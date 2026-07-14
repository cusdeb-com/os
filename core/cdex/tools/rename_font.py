#!/usr/bin/env python3
"""Rename a font family as required by the Ubuntu Font Licence 1.0.

UFL 1.0 clause 2(c): a Modified Version that is not Substantially Changed
must keep the original name with "derivative X" appended. Our modification
is the GASP-table rewrite (tools/gasp_patch.py), which leaves all glyphs
untouched, so the family becomes "Ubuntu derivative CusDeb".

The style (Regular/Bold/Italic) is taken from the font's own nameID 2 and
mirrors the upstream naming convention: the full name is the family for
Regular and "family + style" otherwise.

Usage: rename_font.py <in.ttf> <out.ttf>
"""
import sys

from fontTools.ttLib import TTFont

FAMILY = "Ubuntu derivative CusDeb"
VERSION = "0.83"
POSTSCRIPT_BASE = "Ubuntu-derivativeCusDeb"

# (platformID, platEncID, langID) pairs present in the Ubuntu fonts.
PLATFORMS = [(3, 1, 0x409), (1, 0, 0x0)]


def style_of(font):
    for n in font["name"].names:
        if n.nameID == 2 and (n.platformID, n.platEncID) == (3, 1):
            return str(n)
    raise SystemExit("nameID 2 (subfamily) not found")


def rename(src, dst):
    font = TTFont(src)
    style = style_of(font)
    full = FAMILY if style == "Regular" else f"{FAMILY} {style}"
    postscript = POSTSCRIPT_BASE if style == "Regular" else f"{POSTSCRIPT_BASE}-{style.replace(' ', '')}"
    names = {1: FAMILY, 3: f"{full} {VERSION}", 4: full, 6: postscript}
    # nameID 1 and 4 end up in fixed LF_FACESIZE (32 WCHAR) stack buffers
    # inside Wine; anything that does not fit with its NUL terminator
    # corrupts the stack and aborts the process.
    for name_id in (1, 4):
        if len(names[name_id]) >= 32:
            raise SystemExit(
                f"nameID {name_id} {names[name_id]!r} is {len(names[name_id])} chars;"
                " must be < 32 (LF_FACESIZE)"
            )
    name = font["name"]
    for name_id, value in names.items():
        for platform in PLATFORMS:
            name.setName(value, name_id, *platform)
    font.save(dst)
    print("renamed:", dst, "family:", FAMILY, "style:", style)


if __name__ == "__main__":
    rename(sys.argv[1], sys.argv[2])
