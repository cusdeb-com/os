import struct
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prepare_sxs_manifests import Resource, collect_type_libraries, parse_type_library


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


if __name__ == "__main__":
    unittest.main()
