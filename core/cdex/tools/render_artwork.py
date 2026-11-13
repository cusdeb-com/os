#!/usr/bin/env python3
"""Render the high-DPI start button and Start menu banner bitmaps in artwork/.

Both come from src/media/graphics/start_menu_banner.svg. The banners are the
SVG at each DPI. The start buttons put the SVG's logo on the three state
backgrounds of the 96 DPI Mizu Start::Button image (43x26 per state).

Needs rsvg-convert (librsvg2-bin), URW Gothic in place of the SVG's AvantGarde
font (fonts-urw-base35) and Pillow (python3-pil).

Usage: render_artwork.py <dpi>...
"""
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "src/media/graphics/start_menu_banner.svg")
BUTTON = os.path.join(ROOT, "src/media/themes/Mizu/mizu.msstyles/bitmaps/NORMAL_STARTBUTTON.bmp")
OUT = os.path.join(ROOT, "artwork")
DPIS = [int(arg) for arg in sys.argv[1:]]

FONTS_CONF = """<?xml version="1.0"?>
<fontconfig>
  <include>/etc/fonts/fonts.conf</include>
  <match target="pattern">
    <test name="family"><string>AvantGarde Bk BT</string></test>
    <edit name="family" mode="assign" binding="strong"><string>URW Gothic</string></edit>
  </match>
</fontconfig>
"""


def render(svg, width, height, png, env):
    subprocess.run(["rsvg-convert", "-w", str(width), "-h", str(height), svg, "-o", png],
                   check=True, env=env)
    return Image.open(png).convert("RGBA")


def write_logo_svg(path):
    # The banner without its background rectangles and "ReactOS" text.
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    tree = ET.parse(SVG)
    for parent in list(tree.iter()):
        for child in list(parent):
            if child.get("id") in ("rect4697", "rect4697-4", "text4707"):
                parent.remove(child)
    tree.write(path)


def start_button(logo, scale):
    width, height = round(43 * scale), round(26 * scale)
    mark = logo.rotate(-90, expand=True)
    mark = mark.resize((round(20 * scale), round(18 * scale)), Image.LANCZOS)
    out = Image.new("RGB", (width, 3 * height))
    button = Image.open(BUTTON).convert("RGB")
    for i in range(3):
        # Each 96 DPI state is a fill with a one pixel line on top.
        state = Image.new("RGBA", (width, height), button.getpixel((0, i * 26 + 1)) + (255,))
        state.paste(button.getpixel((0, i * 26)) + (255,), (0, 0, width, round(scale)))
        state.alpha_composite(mark, (round(11 * scale), round(4 * scale)))
        out.paste(state.convert("RGB"), (0, i * height))
    return out


def main():
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, FONTCONFIG_FILE=os.path.join(tmp, "fonts.conf"))
        with open(env["FONTCONFIG_FILE"], "w") as f:
            f.write(FONTS_CONF)

        for dpi in DPIS:
            banner = render(SVG, (21 * dpi + 48) // 96, (233 * dpi + 48) // 96,
                            os.path.join(tmp, "banner.png"), env)
            banner.convert("RGB").save(os.path.join(OUT, f"startmenu-banner-{dpi}.bmp"))

        logo_svg = os.path.join(tmp, "logo.svg")
        write_logo_svg(logo_svg)
        # Render large, then crop to the logo and scale it down per DPI.
        logo = render(logo_svg, 210, 2330, os.path.join(tmp, "logo.png"), env)
        logo = logo.crop(logo.getbbox())
        for dpi in DPIS:
            start_button(logo, dpi / 96).save(os.path.join(OUT, f"start-button-{dpi}.bmp"))


if __name__ == "__main__":
    main()
