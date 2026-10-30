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
    require_linked_sxs_resources,
    require_private_dependencies,
    validate_assembly_manifest,
    xml_tag,
)


def pe_with_manifest(manifest: bytes) -> bytes:
    """Build a minimal x86 PE with one neutral-language RT_MANIFEST resource."""
    resource_size = 96 + len(manifest)
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

    resources = memoryview(image)[0x200:0x200 + resource_size]
    resources[:PE_RESOURCE_DIRECTORY_HEADER.size] = PE_RESOURCE_DIRECTORY_HEADER.pack(
        0, 0, 0, 0, 0, 1,
    )
    resources[16:24] = PE_RESOURCE_DIRECTORY_ENTRY.pack(
        RT_MANIFEST, 0x80000018,
    )
    resources[24:40] = PE_RESOURCE_DIRECTORY_HEADER.pack(0, 0, 0, 0, 0, 1)
    resources[40:48] = PE_RESOURCE_DIRECTORY_ENTRY.pack(1, 0x80000030)
    resources[48:64] = PE_RESOURCE_DIRECTORY_HEADER.pack(0, 0, 0, 0, 0, 1)
    resources[64:72] = PE_RESOURCE_DIRECTORY_ENTRY.pack(0, 80)
    resources[80:96] = PE_RESOURCE_DATA_ENTRY.pack(0x1060, len(manifest), 0, 0)
    resources[96:96 + len(manifest)] = manifest
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

    def test_linked_pe_contains_matching_private_manifest(self):
        manifest = new_manifest({**PRIVATE_IDENTITY, "name": "CusDeb.ReactOS.test.exe"})
        add_private_dependency(manifest)
        manifest_data = ET.tostring(manifest, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "test.exe"
            module.write_bytes(pe_with_manifest(manifest_data))

            linked = read_pe_resources(module)
            compiled = [Resource(
                RT_MANIFEST, 1, RES_METADATA.pack(0, 0, 0, 0, 0), manifest_data,
            )]
            self.assertEqual([(item.type, item.name, item.language, item.data) for item in linked], [
                (RT_MANIFEST, 1, 0, manifest_data),
            ])
            require_linked_sxs_resources(module, compiled, linked)
            require_private_dependencies(module, linked)
            corrupted = [Resource(
                RT_MANIFEST, 1, RES_METADATA.pack(0, 0, 0, 0, 0), b"corrupted",
            )]
            with self.assertRaisesRegex(ValueError, "SxS resources differ"):
                require_linked_sxs_resources(module, corrupted, linked)

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
