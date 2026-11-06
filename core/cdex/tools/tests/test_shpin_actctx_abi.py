import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HEADER = ROOT / "core/cdex/src/dll/win32/shlwapi/sxsactctx.h"
WINE_ACTCTX = ROOT / "core/wine/src/dlls/ntdll/actctx.c"
WINE_COMBASE = ROOT / "core/wine/src/dlls/combase/combase.c"


def struct_fields(source: str, name: str) -> tuple[str, ...]:
    match = re.search(rf"struct\s+{name}\s*\{{(.*?)\}}\s*;", source, re.S)
    if not match:
        raise AssertionError(f"struct {name} not found")
    return tuple(
        re.sub(r"\s+", " ", field).strip()
        for field in match.group(1).split(";")
        if field.strip()
    )


class WineActCtxAbiTests(unittest.TestCase):
    def test_provider_record_matches_wine_producer_and_reader(self):
        provider = struct_fields(HEADER.read_text(), "shpin_comclassredirect_data")
        producer = struct_fields(WINE_ACTCTX.read_text(), "comclassredirect_data")
        reader = struct_fields(WINE_COMBASE.read_text(), "comclassredirect_data")
        self.assertEqual(provider, producer)
        self.assertEqual(provider, reader)

    def test_wine_still_reports_com_section_format_version_one(self):
        source = WINE_ACTCTX.read_text()
        match = re.search(
            r"static NTSTATUS find_comserver_redirection\b(.*?)\nstatic void get_ifaceps_datalen",
            source,
            re.S,
        )
        self.assertIsNotNone(match)
        self.assertRegex(match.group(1), r"data->ulDataFormatVersion\s*=\s*1\s*;")


if __name__ == "__main__":
    unittest.main()
