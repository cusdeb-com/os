import struct
import sys
import tempfile
import unittest
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prepare_sxs_manifests import (
    PE_RESOURCE_DIRECTORY_ENTRY,
    PE_RESOURCE_DIRECTORY_HEADER,
    PE_RESOURCE_DATA_ENTRY,
    PE_SECTION_HEADER,
    PRIVATE_IDENTITY,
    RES_METADATA,
    RT_MANIFEST,
    Resource,
    add_private_dependency,
    collect_type_libraries,
    new_manifest,
    parse_type_library,
    read_pe_resources,
    require_linked_resources,
    require_private_dependencies,
    validate_assembly_manifest,
    xml_tag,
)


def pe_with_resources(resources: list[tuple[int, int, int, bytes]]) -> bytes:
    """Build a minimal x86 PE with ordinal type/name/language resources."""
    types = sorted({resource[0] for resource in resources})
    grouped = {}
    for resource in resources:
        grouped.setdefault(resource[:2], []).append(resource)
    names_by_type = {
        resource_type: sorted(name for kind, name in grouped if kind == resource_type)
        for resource_type in types
    }
    offset = 16 + 8 * len(types)
    type_offsets = {}
    for resource_type in types:
        type_offsets[resource_type] = offset
        offset += 16 + 8 * len(names_by_type[resource_type])

    language_offsets = {}
    for resource_type in types:
        for name in names_by_type[resource_type]:
            language_offsets[(resource_type, name)] = offset
            offset += 16 + 8 * len(grouped[(resource_type, name)])

    data_entry_offsets = {}
    for resource_type, name, language, _ in resources:
        data_entry_offsets[(resource_type, name, language)] = offset
        offset += PE_RESOURCE_DATA_ENTRY.size

    payload_offsets = {}
    for resource_type, name, language, payload in resources:
        offset = (offset + 3) & ~3
        payload_offsets[(resource_type, name, language)] = offset
        offset += len(payload)

    resource_size = offset
    section_size = (resource_size + 0x1FF) & ~0x1FF
    image = bytearray(0x200 + section_size)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"

    coff_offset = 0x84
    image[coff_offset:coff_offset + 20] = struct.pack(
        "<HHIIIHH", 0x014C, 1, 0, 0, 0, 0xE0, 0x2102,
    )
    optional_offset = coff_offset + 20
    struct.pack_into("<H", image, optional_offset, 0x010B)
    struct.pack_into("<I", image, optional_offset + 92, 16)
    struct.pack_into("<II", image, optional_offset + 96 + 2 * 8, 0x1000, resource_size)

    section_offset = optional_offset + 0xE0
    image[section_offset:section_offset + PE_SECTION_HEADER.size] = PE_SECTION_HEADER.pack(
        b".rsrc\0\0\0", resource_size, 0x1000, section_size, 0x200,
    )

    resource_data = memoryview(image)[0x200:0x200 + resource_size]
    resource_data[:16] = PE_RESOURCE_DIRECTORY_HEADER.pack(0, 0, 0, 0, 0, len(types))
    for index, resource_type in enumerate(types):
        resource_data[16 + index * 8:24 + index * 8] = PE_RESOURCE_DIRECTORY_ENTRY.pack(
            resource_type, 0x80000000 | type_offsets[resource_type],
        )
        type_offset = type_offsets[resource_type]
        names = names_by_type[resource_type]
        resource_data[type_offset:type_offset + 16] = PE_RESOURCE_DIRECTORY_HEADER.pack(
            0, 0, 0, 0, 0, len(names),
        )
        for name_index, name in enumerate(names):
            entry_offset = type_offset + 16 + name_index * 8
            resource_data[entry_offset:entry_offset + 8] = PE_RESOURCE_DIRECTORY_ENTRY.pack(
                name, 0x80000000 | language_offsets[(resource_type, name)],
            )

    for (resource_type, name), matching in grouped.items():
        directory_offset = language_offsets[(resource_type, name)]
        resource_data[directory_offset:directory_offset + 16] = PE_RESOURCE_DIRECTORY_HEADER.pack(
            0, 0, 0, 0, 0, len(matching),
        )
        for index, (_, _, language, payload) in enumerate(matching):
            entry_offset = directory_offset + 16 + index * 8
            data_entry_offset = data_entry_offsets[(resource_type, name, language)]
            resource_data[entry_offset:entry_offset + 8] = PE_RESOURCE_DIRECTORY_ENTRY.pack(
                language, data_entry_offset,
            )
            resource_data[data_entry_offset:data_entry_offset + PE_RESOURCE_DATA_ENTRY.size] = (
                PE_RESOURCE_DATA_ENTRY.pack(
                    0x1000 + payload_offsets[(resource_type, name, language)], len(payload), 0, 0,
                )
            )
            payload_offset = payload_offsets[(resource_type, name, language)]
            resource_data[payload_offset:payload_offset + len(payload)] = payload
    return bytes(image)


class TypeLibraryTests(unittest.TestCase):
    def test_extracts_compiled_identity_and_matches_rgs(self):
        tlbid = uuid.UUID("F5078F18-C551-11D3-89B9-0000F81FE221")
        directory = 84
        guid_table = directory + 16 * 16
        data = bytearray(guid_table + 24)
        data[:4] = b"MSFT"
        struct.pack_into("<i", data, 8, 0)
        struct.pack_into("<I", data, 20, 0)
        struct.pack_into("<I", data, 24, (2 << 16) | 3)
        struct.pack_into("<i", data, 32, 0)
        struct.pack_into("<iiii", data, directory + 5 * 16, guid_table, 24, -1, 15)
        data[guid_table:guid_table + 16] = tlbid.bytes_le
        struct.pack_into("<ii", data, guid_table + 16, -2, -1)

        rgs = f"""HKCR
        {{
            NoRemove TypeLib
            {{
                NoRemove '{{{str(tlbid).upper()}}}'
                {{
                    '3.2' = s 'test library'
                    {{ '0' {{ win32 = s '%MODULE%' }} }}
                }}
            }}
        }}""".encode()
        resources = [
            Resource("TYPELIB", 1, b"", bytes(data)),
            Resource("REGISTRY", 1, b"", rgs),
        ]

        library = parse_type_library(bytes(data))
        self.assertEqual((library.tlbid, library.major, library.minor),
                         (f"{{{str(tlbid).upper()}}}", 3, 2))
        self.assertEqual(set(collect_type_libraries("msxml3.dll", resources, {})),
                         {library.key})

    def test_rejects_truncated_resource(self):
        with self.assertRaises(ValueError):
            parse_type_library(b"MSFT")

    def test_linked_pe_preserves_all_resources_and_private_manifest(self):
        manifest = new_manifest({**PRIVATE_IDENTITY, "name": "CusDeb.ReactOS.test.exe"})
        add_private_dependency(manifest)
        manifest_data = ET.tostring(manifest, encoding="utf-8", xml_declaration=True)
        source_resources = [
            (RT_MANIFEST, 1, 0, manifest_data),
            (3, 101, 0, b"icon resource"),
            (16, 1, 0, b"version resource"),
        ]

        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "test.exe"
            module.write_bytes(pe_with_resources(source_resources))

            linked = read_pe_resources(module)
            compiled = [
                Resource(kind, name, RES_METADATA.pack(0, 0, language, 0, 0), payload)
                for kind, name, language, payload in source_resources
            ]
            self.assertCountEqual(
                [(item.type, item.name, item.language, item.data) for item in linked],
                source_resources,
            )
            require_linked_resources(module, compiled, linked)
            require_private_dependencies(module, linked)
            corrupted = [Resource(
                RT_MANIFEST, 1, RES_METADATA.pack(0, 0, 0, 0, 0), b"corrupted",
            )]
            with self.assertRaisesRegex(ValueError, "PE resources differ"):
                require_linked_resources(module, corrupted, linked)
            with self.assertRaisesRegex(ValueError, "PE resources differ"):
                require_linked_resources(module, compiled, linked[:-1])

    def test_assembly_rejects_com_metadata_not_in_linked_resources(self):
        clsid = "{00021401-0000-0000-C000-000000000046}"
        manifest = new_manifest(PRIVATE_IDENTITY)
        provider = ET.SubElement(manifest, xml_tag("file"), {"name": "shell32.dll"})
        ET.SubElement(provider, xml_tag("comClass"), {
            "clsid": clsid,
            "threadingModel": "Apartment",
        })

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CusDeb.ReactOSShell.manifest"
            ET.ElementTree(manifest).write(path, encoding="utf-8", xml_declaration=True)
            with self.assertRaisesRegex(ValueError, "COM classes do not match"):
                validate_assembly_manifest(
                    path,
                    {"shell32.dll"},
                    {clsid: ("shell32.dll", {"clsid": clsid, "threadingModel": "Both"})},
                    {},
                )


if __name__ == "__main__":
    unittest.main()
