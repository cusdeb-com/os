"""Read and write Windows resources used to build the CDEX manifests.

A compiled RES file holds a module's resources before linking; a PE file is
the finished Windows executable, DLL or CPL. This module reads RES records,
writes merged records and extracts resources from linked x86 PE32 files.

Resource type, name and language identify each record. The retained resource
data lets the build preserve existing content and compare linker inputs with
the resources present in the finished module.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

# Win32 RT_MANIFEST type: identifies the XML resources to merge and validate.
RT_MANIFEST = 24

# IMAGE_FILE_MACHINE_I386 in the PE COFF header; reject other payload architectures.
PE_MACHINE_I386 = 0x014C

# PE32 resource directory location and structures used to inspect final modules.
PE_HEADER_POINTER_OFFSET = 0x3C
PE_COFF_HEADER = struct.Struct("<HHIIIHH")
PE_OPTIONAL_HEADER_PE32 = 0x010B
PE_DIRECTORY_COUNT_OFFSET = 92
PE_DATA_DIRECTORY_OFFSET = 96
PE_RESOURCE_DIRECTORY_INDEX = 2
PE_RESOURCE_DIRECTORY_HEADER = struct.Struct("<IIHHHH")
PE_RESOURCE_DIRECTORY_ENTRY = struct.Struct("<II")
PE_RESOURCE_DATA_ENTRY = struct.Struct("<IIII")
PE_SECTION_HEADER = struct.Struct("<8sIIII")
# The structure above reads only the first 24 bytes of the 40-byte section header.
PE_SECTION_HEADER_SIZE = 40
PE_RESOURCE_NAME_FLAG = 0x80000000
PE_RESOURCE_OFFSET_MASK = 0x7FFFFFFF

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


# Read and write compiled RES records and extract resources from linked PE files.


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


class PeResourceReader:
    """Read Win32 resources from a linked x86 PE32 image."""

    def __init__(self, path: Path):
        """Load the PE file and initialize the resource catalog."""
        self.path = path
        self.data = path.read_bytes()
        self.sections = []
        self.resource_offset = 0
        self.resource_size = 0
        self.resources = []
        self.seen = set()

    def read(self) -> list[Resource]:
        """Validate the PE headers and return its resources, or an empty list."""
        if self._read_headers():
            self._collect_resources(0, ())
        return self.resources

    def _fail(self, message: str) -> ValueError:
        """Create a parsing error that identifies the input file."""
        return ValueError(f"Invalid PE resources in {self.path}: {message}")

    def _unpack(self, format_: struct.Struct, offset: int, limit: int | None = None) -> tuple:
        """Read a structure within the file and the optional exclusive limit."""
        end = offset + format_.size
        if offset < 0 or end > len(self.data) or (limit is not None and end > limit):
            raise self._fail("truncated structure")
        return format_.unpack_from(self.data, offset)

    def _read_headers(self) -> bool:
        """Validate PE32 headers and locate the resource directory if present."""
        data = self.data
        if len(data) < 0x40 or data[:2] != b"MZ":
            raise self._fail("missing DOS header")

        pe_offset = struct.unpack_from("<I", data, PE_HEADER_POINTER_OFFSET)[0]
        if data[pe_offset:pe_offset + 4] != b"PE\0\0":
            raise self._fail("missing PE signature")

        coff_offset = pe_offset + 4
        machine, section_count, _, _, _, optional_size, _ = self._unpack(
            PE_COFF_HEADER, coff_offset
        )
        if machine != PE_MACHINE_I386:
            raise self._fail(f"expected i386 machine, found 0x{machine:04x}")

        optional_offset = coff_offset + PE_COFF_HEADER.size
        optional_end = optional_offset + optional_size
        if optional_end > len(data) or optional_size < PE_DATA_DIRECTORY_OFFSET + 8 * (PE_RESOURCE_DIRECTORY_INDEX + 1):
            raise self._fail("truncated PE32 optional header")

        magic, = self._unpack(struct.Struct("<H"), optional_offset, optional_end)
        if magic != PE_OPTIONAL_HEADER_PE32:
            raise self._fail(f"expected PE32 optional header, found 0x{magic:04x}")

        directory_count, = self._unpack(struct.Struct("<I"), optional_offset + PE_DIRECTORY_COUNT_OFFSET, optional_end)
        if directory_count <= PE_RESOURCE_DIRECTORY_INDEX:
            return False

        resource_entry_offset = optional_offset + PE_DATA_DIRECTORY_OFFSET + 8 * PE_RESOURCE_DIRECTORY_INDEX
        resource_rva, self.resource_size = self._unpack(struct.Struct("<II"), resource_entry_offset, optional_end)
        if not resource_rva and not self.resource_size:
            return False
        if not resource_rva or not self.resource_size:
            raise self._fail("incomplete resource data directory")

        for index in range(section_count):
            section_offset = optional_end + index * PE_SECTION_HEADER_SIZE
            _, _, virtual_address, raw_size, raw_offset = self._unpack(PE_SECTION_HEADER, section_offset)
            self.sections.append((virtual_address, raw_size, raw_offset))

        self.resource_offset = self._rva_to_offset(resource_rva, self.resource_size, "resource directory")
        return True

    def _rva_to_offset(self, rva: int, size: int, label: str) -> int:
        """Map a relative virtual address and size to a file offset."""
        for virtual_address, raw_size, raw_offset in self.sections:
            delta = rva - virtual_address
            if delta >= 0 and delta + size <= raw_size:
                file_offset = raw_offset + delta
                if file_offset + size <= len(self.data):
                    return file_offset
        raise self._fail(f"{label} RVA 0x{rva:x} is outside section data")

    def _resource_slice(self, offset: int, size: int, label: str) -> bytes:
        """Read bytes within the resource directory, rejecting invalid bounds."""
        if offset < 0 or size < 0 or offset + size > self.resource_size:
            raise self._fail(f"{label} is outside the resource directory")
        start = self.resource_offset + offset
        if start + size > len(self.data):
            raise self._fail(f"truncated {label}")
        return self.data[start:start + size]

    def _resource_name(self, value: int) -> int | str:
        """Decode a resource entry's numeric identifier or UTF-16 name."""
        if value & PE_RESOURCE_NAME_FLAG:
            offset = value & PE_RESOURCE_OFFSET_MASK
            length, = struct.unpack("<H", self._resource_slice(offset, 2, "resource name"))
            encoded = self._resource_slice(offset + 2, length * 2, "resource name")
            try:
                return encoded.decode("utf-16le")
            except UnicodeDecodeError as error:
                raise self._fail("invalid UTF-16 resource name") from error

        if value > 0xFFFF:
            raise self._fail(f"invalid resource identifier 0x{value:x}")
        return value

    def _collect_resources(self, directory_offset: int, parents: tuple[int | str, ...]) -> None:
        """Collect unique resources from the type/name/language directory tree."""
        header = PE_RESOURCE_DIRECTORY_HEADER.unpack(
            self._resource_slice(directory_offset, PE_RESOURCE_DIRECTORY_HEADER.size, "resource directory header")
        )
        entry_count = header[4] + header[5]
        entries_offset = directory_offset + PE_RESOURCE_DIRECTORY_HEADER.size
        entries_size = entry_count * PE_RESOURCE_DIRECTORY_ENTRY.size
        entries = self._resource_slice(entries_offset, entries_size, "resource directory entries")

        for index in range(entry_count):
            name_value, target = PE_RESOURCE_DIRECTORY_ENTRY.unpack_from(
                entries, index * PE_RESOURCE_DIRECTORY_ENTRY.size
            )
            identifier = self._resource_name(name_value)
            identity = (*parents, identifier)

            if target & PE_RESOURCE_NAME_FLAG:
                if len(identity) >= 3:
                    raise self._fail("resource directory is deeper than type/name/language")
                self._collect_resources(target & PE_RESOURCE_OFFSET_MASK, identity)
                continue

            if len(identity) != 3 or not isinstance(identity[2], int):
                raise self._fail("resource leaf lacks type/name/language identifiers")

            entry_offset = target & PE_RESOURCE_OFFSET_MASK
            data_rva, size, _, _ = PE_RESOURCE_DATA_ENTRY.unpack(
                self._resource_slice(entry_offset, PE_RESOURCE_DATA_ENTRY.size, "resource data entry")
            )
            data_offset = self._rva_to_offset(data_rva, size, "resource data") if size else 0
            payload = self.data[data_offset:data_offset + size] if size else b""
            resource = Resource(
                identity[0], identity[1], RES_METADATA.pack(0, 0, identity[2], 0, 0), payload,
            )
            if resource.key in self.seen:
                raise self._fail(f"duplicate resource {resource.key}")
            self.seen.add(resource.key)
            self.resources.append(resource)


def read_pe_resources(path: Path) -> list[Resource]:
    """Read Win32 resources from a linked x86 PE32 image."""
    return PeResourceReader(path).read()


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
