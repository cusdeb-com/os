"""Find and validate type libraries embedded in CDEX module resources.

A type library describes COM interfaces and carries an identifier and a
version. This module reads those details from compiled MSFT-format type
libraries and compares them with the module's embedded RGS registrations.

The resulting identities are used in the shared SxS manifest. Mismatched
registrations, invalid resources and conflicting providers fail the build;
identical type libraries supplied by multiple modules keep the first provider.
"""

from __future__ import annotations

import re
import struct
import uuid
from dataclasses import dataclass

from com_registry import COM_REGISTRY_RESOURCE_TYPES, GUID_PATTERN, RegistryParser
from resources import Resource

# Compiled type library resources use the Win32 TYPELIB resource type.
TYPELIB_RESOURCE_TYPE = "TYPELIB"

# MSFT type library layout used by the ReactOS resource compiler.
MSFT_TYPELIB_HEADER_SIZE = 84
MSFT_SEGMENT_ENTRY_SIZE = 16
MSFT_SEGMENT_DIRECTORY_ENTRIES = 16
MSFT_GUID_SEGMENT_INDEX = 5
MSFT_GUID_ENTRY_SIZE = 24
MSFT_TYPELIB_GUID_HREFTYPE = -2

# TypeLib registration versions are stored as two-part subkey names in RGS.
TYPELIB_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\Z")


@dataclass(frozen=True)
class TypeLibrary:
    """Identity read from one compiled MSFT TypeLib resource."""

    tlbid: str
    major: int
    minor: int

    @property
    def key(self) -> tuple[str, int, int]:
        """Return the SxS identity shared by a TypeLib GUID and version."""
        return self.tlbid, self.major, self.minor


def parse_type_library(data: bytes) -> TypeLibrary:
    """Read the library GUID and version from a compiled MSFT TypeLib.

    The GUID is stored in the type library's GUID table; all offsets and table
    bounds are validated so a malformed or unsupported resource fails the build.
    """
    if len(data) < MSFT_TYPELIB_HEADER_SIZE or data[:4] != b"MSFT":
        raise ValueError("Unsupported or truncated TypeLib resource (expected MSFT)")

    posguid = struct.unpack_from("<i", data, 8)[0]
    varflags = struct.unpack_from("<I", data, 20)[0]
    packed_version = struct.unpack_from("<I", data, 24)[0]
    typeinfo_count = struct.unpack_from("<i", data, 32)[0]
    if typeinfo_count < 0:
        raise ValueError("Invalid TypeLib type-info count")

    directory = MSFT_TYPELIB_HEADER_SIZE + typeinfo_count * 4
    if varflags & 0x0100:  # HELPDLLFLAG adds one offset before the segment table.
        directory += 4

    directory_end = directory + MSFT_SEGMENT_DIRECTORY_ENTRIES * MSFT_SEGMENT_ENTRY_SIZE
    if directory_end > len(data):
        raise ValueError("Truncated TypeLib segment directory")

    guid_segment = directory + MSFT_GUID_SEGMENT_INDEX * MSFT_SEGMENT_ENTRY_SIZE
    guid_offset, guid_length = struct.unpack_from("<ii", data, guid_segment)
    if (guid_offset < 0 or guid_length < MSFT_GUID_ENTRY_SIZE
            or guid_offset + guid_length > len(data)
            or guid_length % MSFT_GUID_ENTRY_SIZE):
        raise ValueError("Invalid TypeLib GUID table bounds")
    if posguid < 0 or posguid + MSFT_GUID_ENTRY_SIZE > guid_length:
        raise ValueError("Invalid TypeLib library GUID offset")
    if posguid % MSFT_GUID_ENTRY_SIZE:
        raise ValueError("Misaligned TypeLib library GUID offset")

    entry = guid_offset + posguid
    if struct.unpack_from("<i", data, entry + 16)[0] != MSFT_TYPELIB_GUID_HREFTYPE:
        raise ValueError("TypeLib GUID table entry does not identify the library")

    tlbid = "{" + str(uuid.UUID(bytes_le=data[entry:entry + 16])).upper() + "}"
    major = packed_version & 0xFFFF
    minor = packed_version >> 16
    return TypeLibrary(tlbid, major, minor)


def registered_type_libraries(resources: list[Resource]) -> set[tuple[str, int, int]]:
    """Find root HKCR TypeLib registrations that point back to their module."""
    registrations = set()

    for resource in resources:
        if resource.type not in COM_REGISTRY_RESOURCE_TYPES:
            continue

        for root in RegistryParser(resource.data).parse():
            if root.name.casefold() != "hkcr":
                continue

            typelib = root.child("TypeLib")
            if typelib is None:
                continue

            for library in typelib.children:
                if not GUID_PATTERN.fullmatch(library.name):
                    raise ValueError(f"Invalid TypeLib registration GUID: {library.name}")

                for version in library.children:
                    match = TYPELIB_VERSION_PATTERN.fullmatch(version.name)
                    if not match:
                        continue

                    locale = version.child("0")
                    module = locale.child("win32") if locale is not None else None
                    if module is None or module.value not in {"%MODULE%", "%MODULE_RAW%"}:
                        raise ValueError(
                            f"TypeLib registration is not module-private: "
                            f"{library.name} {version.name}"
                        )

                    registrations.add((library.name.upper(), int(match[1]), int(match[2])))

    return registrations


def collect_type_libraries(
    provider: str,
    resources: list[Resource],
    owners: dict[tuple[str, int, int], tuple[str, bytes]],
) -> dict[tuple[str, int, int], TypeLibrary]:
    """Collect TypeLib resources and verify their identities against module RGS."""
    libraries: dict[tuple[str, int, int], tuple[TypeLibrary, bytes]] = {}
    for resource in resources:
        if resource.type != TYPELIB_RESOURCE_TYPE:
            continue

        library = parse_type_library(resource.data)
        previous = libraries.get(library.key)
        if previous is not None and previous[1] != resource.data:
            raise ValueError(f"Conflicting TypeLib resources in {provider}: {library.key}")

        libraries[library.key] = (library, resource.data)

    registrations = registered_type_libraries(resources)
    if registrations != set(libraries):
        missing = sorted(set(libraries) - registrations)
        without_resource = sorted(registrations - set(libraries))
        raise ValueError(
            f"TypeLib/RGS mismatch in {provider}: "
            f"resources without registration={missing}, registrations without resource={without_resource}"
        )

    collected = {}
    for key, (library, data) in libraries.items():
        owner = owners.get(key)
        if owner is not None:
            if owner[1] != data:
                raise ValueError(f"Conflicting TypeLib providers for {key}: {owner[0]} and {provider}")
            print(f"Duplicate TypeLib {key}: keeping {owner[0]}", flush=True)
            continue

        owners[key] = (provider, data)
        collected[key] = library

    return collected
