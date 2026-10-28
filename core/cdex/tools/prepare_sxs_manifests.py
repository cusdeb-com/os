#!/usr/bin/env python3
"""Prepare SxS manifest resources and the shared ReactOS DLL/COM assembly.

The resources command merges a private assembly dependency into each module's
compiled RES records, then produces the COFF object consumed by the linker.
The assembly command validates those dependencies and includes every packaged
DLL/CPL, its COM registrations and embedded TypeLibs in the shared assembly.

Code is grouped into RES records, registry scripts, manifest XML and the two
build commands. Finished PE files are read only to check their architecture.
"""

from __future__ import annotations

import argparse
import re
import struct
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

# Windows assembly schema namespace used for manifest elements.
XML_NAMESPACE = "urn:schemas-microsoft-com:asm.v1"

# ElementTree search alias; manifest serialization uses the default namespace.
XML_NAMESPACES = {"asm": XML_NAMESPACE}

# Shared SxS assembly referenced by every packaged ReactOS module.
ASSEMBLY_NAME = "CusDeb.ReactOSShell"

# Module dependencies and the shared manifest must use this exact identity.
PRIVATE_IDENTITY = {
    "type": "win32",
    "name": ASSEMBLY_NAME,
    "version": "1.0.0.0",
    "processorArchitecture": "x86",
}

# Request themed Common Controls v6 from Wine for the private shell assembly.
COMMON_CONTROLS_IDENTITY = {
    "type": "win32",
    "name": "Microsoft.Windows.Common-Controls",
    "version": "6.0.0.0",
    "processorArchitecture": "*",
    "publicKeyToken": "6595b64144ccf1df",
    "language": "*",
}

# Preserve existing COM mappings when newly included providers repeat a CLSID.
# This ordering affects only duplicate resolution; all payload DLLs/CPLs are included.
COM_PROVIDER_PREFERENCE = (
    "shell32.dll", "shlwapi.dll", "browseui.dll", "rshell.dll",
    "shdocvw.dll", "version.dll", "sendmail.dll", "w32time.dll",
)

# Win32 RT_MANIFEST type: identifies the XML resources to merge and validate.
RT_MANIFEST = 24

# IMAGE_FILE_MACHINE_I386 in the PE COFF header; reject other payload architectures.
PE_MACHINE_I386 = 0x014C

# RES identifier marker: the next WORD is an ordinal instead of UTF-16 text.
RES_ORDINAL_MARKER = 0xFFFF

# Two little-endian DWORDs starting each RES record: DataSize and HeaderSize.
RES_RECORD_SIZES = struct.Struct("<II")

# Fixed 16-byte footer: DataVersion (DWORD), MemoryFlags/LanguageId (WORD each),
# Version/Characteristics (DWORD each). LanguageId distinguishes translations.
RES_METADATA = struct.Struct("<IHHII")

# Required 32-byte RES null record: no data, ordinal type/name 0, zero metadata.
RES_NULL_RECORD = (
    RES_RECORD_SIZES.pack(0, 32)
    + struct.pack("<HHHH", RES_ORDINAL_MARKER, 0, RES_ORDINAL_MARKER, 0)
    + RES_METADATA.pack(0, 0, 0, 0, 0)
)

# Accept complete brace-delimited CLSIDs before emitting COM class declarations.
GUID_PATTERN = re.compile(r"\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\}\Z")

# Match quoted values and GUIDs before braces/words so they remain single tokens.
RGS_TOKEN_PATTERN = re.compile(
    r"'(?:[^']|'')*'"         # Single-quoted string, with doubled quote escapes.
    r'|"[^"]*"'              # Double-quoted string.
    r"|\{[0-9a-fA-F-]{36}\}"  # A GUID is one token, not a nested block.
    r"|[{}=]"
    r"|[^\s{}=]+"
)

# RGS prefixes consumed before the actual registry key or value name.
RGS_MODIFIERS = {"noremove", "forceremove", "delete", "remove", "val"}

# ReactOS and Wine resource compilers use different names for the same RGS data.
COM_REGISTRY_RESOURCE_TYPES = {"REGISTRY", "WINE_REGISTRY"}

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

# SxS threadingModel values accepted when exporting InprocServer32 metadata.
COM_THREADING_MODELS = {"Apartment", "Both", "Free", "Neutral"}

ET.register_namespace("", XML_NAMESPACE)


# Win32 resource records


@dataclass
class Resource:
    """One RES record, keeping its original header and replaceable payload.

    The raw header preserves language, flags and version metadata when a
    manifest's XML changes. Only the payload size is updated during writing.
    """

    type: int | str
    name: int | str
    header: bytes
    data: bytes

    @property
    def language(self) -> int:
        """Return the language ID stored in the record's metadata footer."""
        metadata_offset = len(self.header) - RES_METADATA.size
        _, _, language, _, _ = RES_METADATA.unpack_from(self.header, metadata_offset)
        return language

    @property
    def key(self) -> tuple[int | str, int | str, int]:
        """Return the type/name/language identity used to detect duplicates."""
        return self.type, self.name, self.language

    def write(self, output: BinaryIO) -> None:
        """Write this record with its current payload and DWORD padding."""
        header = bytearray(self.header)
        struct.pack_into("<I", header, 0, len(self.data))

        output.write(header)
        output.write(self.data)
        output.write(b"\0" * (-len(self.data) % 4))


def read_resource_identifier(data: bytes, offset: int, limit: int) -> tuple[int | str, int]:
    """Return an ordinal or UTF-16 name and the byte offset after it.

    ``limit`` is the exclusive end of the identifier area, before the record's
    metadata. Truncated ordinals and unterminated names raise ValueError.
    """
    if offset + 2 > limit:
        raise ValueError("Truncated resource identifier")

    value = struct.unpack_from("<H", data, offset)[0]
    if value == RES_ORDINAL_MARKER:
        if offset + 4 > limit:
            raise ValueError("Truncated resource ordinal")
        return struct.unpack_from("<H", data, offset + 2)[0], offset + 4

    start = offset
    while offset + 2 <= limit:
        if data[offset:offset + 2] == b"\0\0":
            return data[start:offset].decode("utf-16le"), offset + 2

        offset += 2

    raise ValueError("Unterminated resource name")


def read_res(path: Path) -> list[Resource]:
    """Read compiled RES records, excluding the stream's empty first record.

    Original header and payload bytes are retained for later merging. Invalid
    record bounds or identifiers fail instead of returning partial resources.
    """
    data = path.read_bytes()
    resources = []
    offset = 0

    while offset < len(data):
        data_size, header_size = RES_RECORD_SIZES.unpack_from(data, offset)
        header_end = offset + header_size
        if header_size < 24 or header_end + data_size > len(data):
            raise ValueError(f"Invalid resource record in {path}")

        metadata_offset = header_end - RES_METADATA.size
        resource_type, position = read_resource_identifier(data, offset + 8, metadata_offset)
        resource_name, _ = read_resource_identifier(data, position, metadata_offset)

        if resource_type != 0 or resource_name != 0 or data_size:
            resources.append(Resource(
                resource_type, resource_name,
                data[offset:header_end], data[header_end:header_end + data_size],
            ))

        offset = (header_end + data_size + 3) & ~3  # Records are DWORD-aligned.

    return resources


def write_res(path: Path, resources: list[Resource], module_name: str) -> None:
    """Write a RES stream, rejecting duplicate type/name/language identities.

    ``module_name`` identifies the module in duplicate-resource diagnostics.
    The caller supplies a temporary path so a failure cannot replace an output.
    """
    seen = set()

    with path.open("wb") as output:
        output.write(RES_NULL_RECORD)
        for resource in resources:
            if resource.key in seen:
                raise ValueError(f"Duplicate resource in {module_name}: {resource.key}")

            seen.add(resource.key)
            resource.write(output)


# ATL registry scripts and COM metadata


@dataclass
class RegistryNode:
    """An RGS registry key or value with its nested entries."""

    name: str
    value: str | None = None
    children: list[RegistryNode] = field(default_factory=list)

    def child(self, name: str) -> RegistryNode | None:
        """Find the first direct child by case-insensitive registry name."""
        for node in self.children:
            if node.name.casefold() == name.casefold():
                return node

        return None


class RegistryParser:
    """Parse ATL RGS resources into registry nodes using a token cursor.

    Registration modifiers and value type tokens are consumed; key names,
    values and nesting are retained for COM class extraction.
    """

    def __init__(self, data: bytes):
        """Decode UTF-8 or BOM-marked UTF-16 input and tokenize its RGS text."""
        encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        text = data.decode(encoding).rstrip("\x00")
        text = re.sub(r"(?m)^\s*//.*$", "", text)

        self.tokens = RGS_TOKEN_PATTERN.findall(text)
        self.position = 0

    def parse(self) -> list[RegistryNode]:
        """Consume the whole script and return its top-level registry nodes."""
        nodes = self._entries()
        if self.position != len(self.tokens):
            raise ValueError("Unexpected trailing RGS tokens")

        return nodes

    def _take(self) -> str:
        """Advance one token, unquote strings and reject premature EOF."""
        if self.position == len(self.tokens):
            raise ValueError("Truncated RGS resource")

        token = self.tokens[self.position]
        self.position += 1

        if token.startswith(("'", '"')):
            return token[1:-1].replace("''", "'")

        return token

    def _entries(self, nested: bool = False) -> list[RegistryNode]:
        """Read sibling entries and consume the closing brace of a nested block."""
        nodes = []

        while self.position < len(self.tokens) and self.tokens[self.position] != "}":
            name = self._take()
            if name.casefold() in RGS_MODIFIERS:
                name = self._take()

            node = RegistryNode(name)

            if self.position < len(self.tokens) and self.tokens[self.position] == "=":
                self._take()  # Equals sign.
                self._take()  # Registry value type.
                node.value = self._take()

            if self.position < len(self.tokens) and self.tokens[self.position] == "{":
                self._take()
                node.children = self._entries(nested=True)

            nodes.append(node)

        if nested and self._take() != "}":
            raise ValueError("Unbalanced RGS resource")

        return nodes


def com_classes(nodes: list[RegistryNode]) -> Iterator[dict[str, str]]:
    """Yield manifest attributes for COM classes implemented by this module.

    Only InprocServer32 entries referring to the RGS module placeholder are
    included. Invalid CLSIDs and unsupported threading models raise ValueError.
    """
    for node in nodes:
        if node.name.casefold() == "clsid":
            for cls in node.children:
                server = cls.child("InprocServer32")
                if server is None or server.value not in {"%MODULE%", "%MODULE_RAW%"}:
                    continue

                if not GUID_PATTERN.fullmatch(cls.name):
                    raise ValueError(f"Unresolved COM class: {cls.name}")

                attributes = {"clsid": cls.name.upper()}

                model = server.child("ThreadingModel")
                if model is not None:
                    if model.value not in COM_THREADING_MODELS:
                        raise ValueError(f"Unsupported threading model: {model.value}")
                    attributes["threadingModel"] = model.value

                progid = cls.child("ProgID")
                if progid is not None and progid.value:
                    attributes["progid"] = progid.value

                yield attributes

        yield from com_classes(node.children)


def collect_com_classes(
    provider: str,
    resources: list[Resource],
    owners: dict[str, tuple[str, dict[str, str]]],
) -> dict[str, dict[str, str]]:
    """Collect one provider's COM classes, keyed by CLSID.

    ``owners`` is shared across providers and updated in place. Existing
    providers keep identical mappings when new modules repeat a CLSID;
    conflicting mappings and duplicates among new providers are rejected.
    """
    classes = {}
    for resource in resources:
        if resource.type not in COM_REGISTRY_RESOURCE_TYPES:
            continue

        nodes = RegistryParser(resource.data).parse()
        for attributes in com_classes(nodes):
            clsid = attributes["clsid"]
            owner = owners.get(clsid)

            if owner is not None and owner[0] != provider:
                if (owner[0] in COM_PROVIDER_PREFERENCE
                        and provider not in COM_PROVIDER_PREFERENCE
                        and owner[1] == attributes):
                    print(f"Duplicate COM class {clsid}: keeping {owner[0]}", flush=True)
                    continue

                raise ValueError(
                    f"COM class {clsid} is supplied by both {owner[0]} and {provider}"
                )
            if owner is not None and owner[1] != attributes:
                raise ValueError(f"Conflicting COM metadata for {clsid}")

            owners[clsid] = (provider, attributes)
            classes[clsid] = attributes
    return classes


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


# Manifest XML


def xml_tag(name: str) -> str:
    """Qualify an element name with the Windows assembly XML namespace."""
    return f"{{{XML_NAMESPACE}}}{name}"


def new_manifest(identity: dict[str, str]) -> ET.Element:
    """Create an assembly root containing the supplied assembly identity."""
    root = ET.Element(xml_tag("assembly"), manifestVersion="1.0")
    ET.SubElement(root, xml_tag("assemblyIdentity"), identity)
    return root


def private_dependencies(root: ET.Element) -> list[ET.Element]:
    """Return the direct dependency identities referring to our private assembly."""
    identities = root.findall(
        "asm:dependency/asm:dependentAssembly/asm:assemblyIdentity", XML_NAMESPACES,
    )

    return [identity for identity in identities if identity.get("name") == ASSEMBLY_NAME]


def add_private_dependency(root: ET.Element) -> None:
    """Add the private dependency in place, accepting an existing matching one.

    An existing dependency with conflicting identity attributes raises
    ValueError. Unrelated manifest elements are preserved.
    """
    for identity in private_dependencies(root):
        if identity.attrib != PRIVATE_IDENTITY:
            raise ValueError("Conflicting private assembly identity")

        return

    dependency = ET.SubElement(root, xml_tag("dependency"))
    dependent_assembly = ET.SubElement(dependency, xml_tag("dependentAssembly"))
    ET.SubElement(dependent_assembly, xml_tag("assemblyIdentity"), PRIVATE_IDENTITY)


def manifest_ids(kind: str) -> tuple[int, ...]:
    """Return relevant manifest IDs, primary first: EXE 1 or DLL 2 and 123."""
    return (1,) if kind == "exe" else (2, 123)


def merge_manifest_dependencies(resources: list[Resource], kind: str) -> bool:
    """Attach the dependency and report whether a primary manifest was present."""
    ids = manifest_ids(kind)
    primary_found = False

    for resource in resources:
        if resource.type != RT_MANIFEST or resource.name not in ids:
            continue

        root = ET.fromstring(resource.data)
        add_private_dependency(root)
        resource.data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        if resource.name == ids[0]:
            primary_found = True

    return primary_found


def require_private_dependencies(module: Path, resources: list[Resource]) -> None:
    """Require exactly one matching private dependency in each relevant manifest.

    Reject modules without a relevant manifest and manifests with missing,
    duplicate or conflicting private dependency identities.
    """
    kind = "exe" if module.suffix.lower() == ".exe" else "dll"
    manifests = [
        resource for resource in resources
        if resource.type == RT_MANIFEST and resource.name in manifest_ids(kind)
    ]
    if not manifests:
        raise ValueError(f"Private dependency missing: {module.name}")

    for manifest in manifests:
        identities = private_dependencies(ET.fromstring(manifest.data))
        if len(identities) != 1 or identities[0].attrib != PRIVATE_IDENTITY:
            raise ValueError(f"Private dependency missing: {module.name}")


def write_xml(root: ET.Element, path: Path) -> None:
    """Write a UTF-8 manifest with an XML declaration."""
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


# Resource preparation before linking


def create_default_manifest_resource(
    module: str, resource_id: int, compiler: str, work: Path,
) -> list[Resource]:
    """Compile a neutral-language primary manifest using temporary files.

    The manifest identifies ``module`` and depends on the private assembly.
    Return the compiler's RES records for inclusion in the module's resources.
    """
    identity = {**PRIVATE_IDENTITY, "name": f"CusDeb.ReactOS.{module}"}
    root = new_manifest(identity)
    add_private_dependency(root)

    manifest = work / "default.xml"
    write_xml(root, manifest)

    rc_file = work / "default.rc"
    res_file = work / "default.res"
    rc_file.write_text(f'LANGUAGE 0, 0\n{resource_id} {RT_MANIFEST} "{manifest}"\n')

    subprocess.run([
        compiler, "-J", "rc", "-O", "res", str(rc_file), str(res_file),
    ], check=True)

    return read_res(res_file)


def prepare_resources(args: argparse.Namespace) -> None:
    """Handle resources: merge manifests, compile COFF and publish both outputs.

    A missing primary manifest is created. RES and COFF files are prepared in
    a temporary directory; each destination is replaced only after compilation.
    """
    resources = []
    for source in args.inputs:
        resources.extend(read_res(source))

    primary_found = merge_manifest_dependencies(resources, args.kind)

    with tempfile.TemporaryDirectory(dir=args.output.parent) as directory:
        work = Path(directory)

        if not primary_found:
            resources.extend(create_default_manifest_resource(
                args.module, manifest_ids(args.kind)[0], args.compiler, work,
            ))

        res_file = work / "merged.res"
        object_file = work / "merged.obj"
        write_res(res_file, resources, args.module)

        subprocess.run([
            args.compiler, "-J", "res", "-O", "coff", str(res_file), str(object_file),
        ], check=True)

        res_file.replace(args.output)
        object_file.replace(args.object)


# Shared assembly generation during packaging


def load_module_resources(payload: Path, resource_directory: Path) -> dict[str, list[Resource]]:
    """Load and validate the resource catalog for every packaged EXE, DLL and CPL.

    PE headers must identify i386 modules. Each build-generated .res-path
    index points to the compiled RES file whose private dependencies are checked.
    """
    modules = sorted(
        path for path in payload.iterdir() if path.suffix.lower() in {".exe", ".dll", ".cpl"}
    )
    catalogs = {}

    for module in modules:
        data = module.read_bytes()
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]  # DOS header e_lfanew.
        signature = data[pe_offset:pe_offset + 4]
        machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
        if signature != b"PE\0\0" or machine != PE_MACHINE_I386:
            raise ValueError(f"Expected an i386 PE module: {module}")

        index = resource_directory / f"{module.name}.res-path"
        resources = read_res(Path(index.read_text()))
        require_private_dependencies(module, resources)
        catalogs[module.name] = resources

    return catalogs


def prepare_assembly(args: argparse.Namespace) -> None:
    """Write the shared manifest from every packaged DLL/CPL and its resources."""
    catalogs = load_module_resources(args.payload, args.resources)

    assembly = new_manifest(PRIVATE_IDENTITY)
    dependency = ET.SubElement(assembly, xml_tag("dependency"))
    dependent_assembly = ET.SubElement(dependency, xml_tag("dependentAssembly"))
    ET.SubElement(dependent_assembly, xml_tag("assemblyIdentity"), COMMON_CONTROLS_IDENTITY)

    owners: dict[str, tuple[str, dict[str, str]]] = {}
    typelib_owners: dict[tuple[str, int, int], tuple[str, bytes]] = {}
    provider_set = {
        module for module in catalogs
        if Path(module).suffix.lower() in {".dll", ".cpl"}
    }
    providers = [module for module in COM_PROVIDER_PREFERENCE if module in provider_set]
    providers.extend(sorted(provider_set - set(providers)))
    for provider in providers:
        provider_element = ET.SubElement(assembly, xml_tag("file"), name=provider)
        typelibs = collect_type_libraries(provider, catalogs[provider], typelib_owners)
        for key in sorted(typelibs):
            library = typelibs[key]
            ET.SubElement(provider_element, xml_tag("typelib"), {
                "tlbid": library.tlbid,
                "version": f"{library.major}.{library.minor}",
                "helpdir": "",
            })

        classes = collect_com_classes(provider, catalogs[provider], owners)

        for clsid in sorted(classes):
            ET.SubElement(provider_element, xml_tag("comClass"), classes[clsid])

        print(f"Private provider: {provider}, COM classes: {len(classes)}", flush=True)

    write_xml(assembly, args.payload / f"{ASSEMBLY_NAME}.manifest")


def main() -> None:
    """Parse build command arguments and dispatch to the selected stage."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)

    resources = commands.add_parser("resources", help="Embed private dependencies before linking")
    resources.add_argument("--compiler", required=True)
    resources.add_argument("--kind", choices=("exe", "dll"), required=True)
    resources.add_argument("--module", required=True)
    resources.add_argument("--output", type=Path, required=True)
    resources.add_argument("--object", type=Path, required=True)
    resources.add_argument("--inputs", type=Path, nargs="*", default=[])
    resources.set_defaults(handler=prepare_resources)

    assembly = commands.add_parser("assembly", help="Generate the shared DLL/COM assembly")
    assembly.add_argument("--payload", type=Path, required=True)
    assembly.add_argument("--resources", type=Path, required=True)
    assembly.set_defaults(handler=prepare_assembly)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
