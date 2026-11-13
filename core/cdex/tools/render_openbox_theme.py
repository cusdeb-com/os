#!/usr/bin/env python3
"""Render the high-DPI variants of the Openbox Win10 theme.

Openbox draws the title bar buttons from fixed-size bitmaps and takes the
border and menu metrics from themerc as pixels. runtime/themes/Win10 is the
96 DPI theme; this writes <output directory>/Win10-<dpi>, where the button
shapes are drawn at the pixel size of each DPI and the themerc lengths are
scaled.

Usage: render_openbox_theme.py <output directory> <dpi>...
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEMERC = os.path.join(ROOT, "runtime/themes/Win10/openbox-3/themerc")

# Shapes on the 96 DPI pixel grid: (name in the bitmap, size, primitives).
# "line" is horizontal, vertical or at 45 degrees; "box" is filled.
SHAPES = {
    "close": ("close", 10, [("line", 1, 1, 8, 8), ("line", 8, 1, 1, 8)]),
    "iconify": ("iconify", 10, [("line", 0, 5, 9, 5)]),
    "shade": ("shade", 10, [("line", 0, 4, 9, 4)]),
    "max": ("max", 10, [("line", 0, 0, 9, 0), ("line", 0, 9, 9, 9),
                        ("line", 0, 0, 0, 9), ("line", 9, 0, 9, 9)]),
    "max_toggled": ("max_toggled", 10, [
        ("line", 2, 0, 9, 0), ("line", 9, 0, 9, 7), ("line", 2, 0, 2, 2), ("line", 7, 7, 9, 7),
        ("line", 0, 2, 7, 2), ("line", 0, 9, 7, 9), ("line", 0, 2, 0, 9), ("line", 7, 2, 7, 9)]),
    "bullet": ("bullet2", 13, [("line", 3, 0, 9, 6), ("line", 9, 6, 3, 12)]),
    "desk": ("desk", 16, [
        ("line", 0, 0, 0, 2), ("line", 10, 0, 10, 2), ("line", 0, 2, 10, 2), ("line", 14, 0, 14, 2),
        ("line", 0, 4, 10, 4), ("line", 0, 10, 10, 10), ("line", 0, 4, 0, 10), ("line", 10, 4, 10, 10),
        ("box", 13, 4, 15, 6), ("line", 14, 8, 14, 14),
        ("line", 0, 12, 10, 12), ("line", 0, 12, 0, 14), ("line", 10, 12, 10, 14)]),
    "desk_hover": ("desk_hover", 16, [
        ("line", 0, 0, 10, 0), ("line", 0, 6, 10, 6), ("line", 0, 0, 0, 6), ("line", 10, 0, 10, 6),
        ("line", 14, 0, 14, 6), ("box", 13, 8, 15, 10), ("line", 14, 12, 14, 14),
        ("line", 0, 8, 10, 8), ("line", 0, 14, 10, 14), ("line", 0, 8, 0, 14), ("line", 10, 8, 10, 14)]),
}
# themerc lengths that follow the DPI.
LINE_KEYS = ("border.width", "menu.border.width", "menu.separator.width",
             "menu.overlap.x", "menu.overlap.y")
LENGTH_KEYS = ("menu.separator.padding.width", "menu.separator.padding.height")


def half_up(value):
    return int(value + 0.5)


def render(size, primitives, scale, pen):
    """Return the scaled size and the set of pixels of a shape drawn with a pen-wide line."""
    scaled = 2 * half_up((size - 1) * scale / 2) + pen
    pixels = set()

    def at(coord):
        return half_up(coord * (scaled - pen) / (size - 1))

    for kind, x0, y0, x1, y1 in primitives:
        x0, y0, x1, y1 = at(x0), at(y0), at(x1), at(y1)
        if kind == "box" or x0 == x1 or y0 == y1:
            pixels.update((x, y) for x in range(x0, x1 + pen) for y in range(y0, y1 + pen))
            continue
        assert abs(x1 - x0) == y1 - y0
        # A pen-wide line through the centres of its end boxes: the pixels
        # whose centre is within half a pen width of it.
        span = y1 - y0 + pen
        for row in range(span):
            for col in range(span):
                across = (col if x1 > x0 else span - 1 - col) - row
                if 2 * across * across <= pen * pen:
                    pixels.add((min(x0, x1) + col, y0 + row))
    return scaled, pixels


def write_xbm(path, name, size, pixels):
    stride = (size + 7) // 8
    data = bytearray(stride * size)
    for x, y in pixels:
        data[y * stride + x // 8] |= 1 << (x % 8)
    rows = ",\n   ".join(", ".join(f"0x{b:02x}" for b in data[i:i + 12])
                         for i in range(0, len(data), 12))
    with open(path, "w") as out:
        out.write(f"#define {name}_width {size}\n#define {name}_height {size}\n")
        out.write(f"static unsigned char {name}_bits[] = {{\n   {rows} }};\n")


def main():
    with open(THEMERC) as src:
        themerc = src.read()
    for dpi in sys.argv[2:]:
        dpi = int(dpi)
        scale = dpi / 96
        # Lines stay one pixel wide below 168 DPI, as in the 96 DPI theme.
        pen = max(1, int(scale + 0.25))
        out = os.path.join(sys.argv[1], f"Win10-{dpi}/openbox-3")
        os.makedirs(out, exist_ok=True)
        for file_name, (name, size, primitives) in SHAPES.items():
            scaled, pixels = render(size, primitives, scale, pen)
            write_xbm(os.path.join(out, file_name + ".xbm"), name, scaled, pixels)

        def length(match):
            value = int(match.group(2))
            value = value * pen if match.group(1) in LINE_KEYS else half_up(value * scale)
            return f"{match.group(1)}: {value}"

        keys = "|".join(re.escape(key) for key in LINE_KEYS + LENGTH_KEYS)
        with open(os.path.join(out, "themerc"), "w") as dst:
            dst.write(re.sub(rf"^({keys}): (-?\d+)$", length, themerc, flags=re.M))


if __name__ == "__main__":
    main()
