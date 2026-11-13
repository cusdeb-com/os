#!/usr/bin/env python3
"""Render the high-DPI glyphs of the Mizu theme in artwork/.

The 96 DPI bitmaps in src/media/themes/Mizu/mizu.msstyles/bitmaps supply the
colours of every state. The shapes (arrows, chevrons, grip dots, radio
circles, check marks) are drawn here at the pixel size of each DPI, so nothing is
resampled. NormalNormal.INI selects the results with ImageSelectType = Dpi.

Needs Pillow (python3-pil).

Usage: render_theme_glyphs.py <dpi>...
"""
import math
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src/media/themes/Mizu/mizu.msstyles/bitmaps")
OUT = os.path.join(ROOT, "artwork")
DPIS = [int(arg) for arg in sys.argv[1:]]

MAGENTA = (255, 0, 255)
# Ring width of the eight radio button states at 96 DPI.
RADIO_RING = (1, 1, 2, 1, 1, 1, 2, 1)


def load(name, count, horizontal=False):
    """Return the states of a 96 DPI theme bitmap."""
    image = Image.open(os.path.join(SRC, f"NORMAL_{name}.bmp")).convert("RGB")
    width, height = image.size
    if horizontal:
        step = width // count
        return [image.crop((i * step, 0, (i + 1) * step, height)) for i in range(count)]
    step = height // count
    return [image.crop((0, i * step, width, (i + 1) * step)) for i in range(count)]


def save(states, name, dpi, horizontal=False):
    width, height = states[0].size
    if horizontal:
        out = Image.new("RGB", (width * len(states), height))
    else:
        out = Image.new("RGB", (width, height * len(states)))
    for i, state in enumerate(states):
        out.paste(state, (i * width, 0) if horizontal else (0, i * height))
    out.save(os.path.join(OUT, f"mizu-{name}-{dpi}.bmp"))


def odd(value):
    return int(value) // 2 * 2 + 1


def nearest_odd(value):
    """The odd number closest to value, the lower one on a tie."""
    return 2 * math.ceil(value / 2) - 1


def triangle(direction, base):
    """Pixels of a stepped triangle with an odd base, as the theme draws its arrows."""
    depth = (base + 1) // 2
    pixels = []
    for d in range(depth):
        for i in range(d, base - d):
            if direction == "down":
                pixels.append((i, d, d))
            elif direction == "up":
                pixels.append((i, depth - 1 - d, d))
            elif direction == "right":
                pixels.append((d, i, d))
            else:
                pixels.append((depth - 1 - d, i, d))
    size = (base, depth) if direction in ("up", "down") else (depth, base)
    return size, pixels


def shape_box(state, background):
    points = [(x, y) for y in range(state.height) for x in range(state.width)
              if state.getpixel((x, y)) not in background]
    if not points:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def depth_colours(state, box, direction, background):
    """Colour of each step of a 96 DPI arrow, from its base to its tip."""
    left, top, right, bottom = box
    colours = []
    if direction in ("up", "down"):
        rows = range(top, bottom) if direction == "down" else range(bottom - 1, top - 1, -1)
        lines = [[state.getpixel((x, y)) for x in range(left, right)] for y in rows]
    else:
        cols = range(left, right) if direction == "right" else range(right - 1, left - 1, -1)
        lines = [[state.getpixel((x, y)) for y in range(top, bottom)] for x in cols]
    for line in lines:
        line = [c for c in line if c not in background]
        colours.append(line[len(line) // 2])
    return colours


def draw_arrow(out, state, box, direction, background, scale, centre=None):
    """Draw the arrow found in box of a 96 DPI state into out, enlarged by scale."""
    left, top, right, bottom = box
    base = right - left if direction in ("up", "down") else bottom - top
    (width, height), pixels = triangle(direction, odd(base * scale))
    colours = depth_colours(state, box, direction, background)
    depth = max(p[2] for p in pixels) + 1
    if centre is None:
        centre = ((left + right) * scale / 2, (top + bottom) * scale / 2)
    x0 = min(max(round(centre[0] - width / 2), 0), out.width - width)
    y0 = min(max(round(centre[1] - height / 2), 0), out.height - height)
    for x, y, d in pixels:
        out.putpixel((x0 + x, y0 + y), colours[d * len(colours) // depth])


def arrow_glyphs(name, count, direction, out_name):
    """Arrow glyphs on the transparent colour (combo box, spin, split button)."""
    states = load(name, count)
    for dpi in DPIS:
        scale = dpi / 96
        result = []
        for state in states:
            box = shape_box(state, (MAGENTA,))
            width = max(round(state.width * scale), odd((box[2] - box[0]) * scale))
            height = max(round(state.height * scale), odd((box[3] - box[1]) * scale))
            out = Image.new("RGB", (width, height), MAGENTA)
            draw_arrow(out, state, box, direction, (MAGENTA,), scale)
            result.append(out)
        save(result, out_name, dpi)


def scroll_arrows():
    """Scroll bar buttons: border and fill of each state with the arrow drawn in."""
    states = load("SCROLLARROWS", 16)
    for dpi in DPIS:
        # The scroll bar width, SM_CXVSCROLL: 17 pixels at 96 DPI.
        size = int(17 * dpi / 96 + 0.5)
        result = []
        for i, state in enumerate(states):
            direction = ("up", "down", "left", "right")[i // 4]
            fill = state.getpixel((2, 2))
            last = state.width - 1
            out = Image.new("RGB", (size, size), fill)
            draw = ImageDraw.Draw(out)
            # The side that faces the scroll bar track has no border.
            for edge, src, line in ((0, (7, 0), (0, 0, size - 1, 0)),
                                    (1, (7, last), (0, size - 1, size - 1, size - 1)),
                                    (2, (0, 7), (0, 0, 0, size - 1)),
                                    (3, (last, 7), (size - 1, 0, size - 1, size - 1))):
                if state.getpixel(src) != fill:
                    draw.line(line, fill=state.getpixel(src))
            inner = state.crop((1, 1, last, last))
            box = shape_box(inner, (fill,))
            # At 96 DPI the 15 pixel image is stretched over the 17 pixel
            # button, which widens its 7 pixel arrow to 9.
            draw_arrow(out, inner, box, direction, (fill,), size * 9 / (17 * 7),
                       (size / 2, size / 2))
            result.append(out)
        save(result, "scroll-arrows", dpi)


def tree_glyphs():
    """Tree view expanders: a bordered box with an arrow."""
    states = load("TREEEXPANDCOLLAPSE", 2)
    for dpi in DPIS:
        scale = dpi / 96
        size = odd(states[0].width * scale)
        result = []
        for state, direction in zip(states, ("down", "up")):
            fill = state.getpixel((1, 1))
            out = Image.new("RGB", (size, size), fill)
            ImageDraw.Draw(out).rectangle((0, 0, size - 1, size - 1),
                                          outline=state.getpixel((0, 0)))
            inner = state.crop((1, 1, state.width - 1, state.height - 1))
            draw_arrow(out, inner, shape_box(inner, (fill,)), direction, (fill,), scale,
                       (size / 2, size / 2))
            result.append(out)
        save(result, "tree-glyph", dpi)


def chevrons():
    """Toolbar overflow chevrons: two ">" strokes at the bottom right of the glyph."""
    states = load("CHEVRON", 6)
    for dpi in DPIS:
        scale = dpi / 96
        height, thickness = odd(5 * scale), round(2 * scale)
        half = height // 2
        result = []
        for state in states:
            box = shape_box(state, (MAGENTA,))
            colour = state.getpixel((box[0], box[3] - 1))
            out = Image.new("RGB", (round(state.width * scale), round(state.height * scale)),
                            MAGENTA)
            x0 = out.width - (half + 3 * thickness)
            y0 = out.height - height
            for row in range(height):
                offset = min(row, height - 1 - row)
                for start in (0, 2 * thickness):
                    for x in range(thickness):
                        out.putpixel((x0 + start + offset + x, y0 + row), colour)
            result.append(out)
        save(result, "chevron", dpi)


def resize_grips():
    """Size grips: three diagonal rows of dots, each a grey square over a white one."""
    states = load("RESIZEGRIP2", 2, horizontal=True)
    background = states[0].getpixel((0, 0))
    dark, light = states[0].getpixel((14, 9)), states[0].getpixel((14, 10))
    for dpi in DPIS:
        scale = dpi / 96
        dot = max(1, int(scale + 0.5))
        out = Image.new("RGB", (round(16 * scale), round(17 * scale)), background)
        draw = ImageDraw.Draw(out)
        right, bottom = out.width - round(scale), out.height - round(2 * scale)
        for column in range(3):
            for row in range(3 - column):
                x = right - dot - column * 2 * dot
                y = bottom - 2 * dot - row * 2 * dot
                draw.rectangle((x, y, x + dot - 1, y + dot - 1), fill=dark)
                draw.rectangle((x, y + dot, x + dot - 1, y + 2 * dot - 1), fill=light)
        save([out, out.transpose(Image.FLIP_LEFT_RIGHT)], "resize-grip", dpi, horizontal=True)


def disc(size, radius, supersample=8):
    """Coverage (0..1 per pixel) of a centred disc."""
    big = size * supersample
    mask = Image.new("L", (big, big), 0)
    centre, r = big / 2, radius * supersample
    ImageDraw.Draw(mask).ellipse((centre - r, centre - r, centre + r - 1, centre + r - 1), fill=255)
    return [v / 255 for v in mask.resize((size, size), Image.BOX).getdata()]


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def radio_buttons():
    """Radio buttons: an antialiased ring, its fill and the dot of the checked states."""
    states = load("RADIOBUTTON13", 8)
    for dpi in DPIS:
        # An odd size keeps the dot centred on a pixel.
        size = nearest_odd(states[0].width * dpi / 96)
        scale = size / states[0].width
        outer = disc(size, size / 2)
        result = []
        for i, state in enumerate(states):
            ring, fill = state.getpixel((7, 0)), state.getpixel((7, 3))
            dot_colour = state.getpixel((7, 7))
            inner = disc(size, size / 2 - RADIO_RING[i] * scale)
            dot = disc(size, 3.2 * scale)
            out = Image.new("RGB", (size, size), MAGENTA)
            for n in range(size * size):
                # Like the 96 DPI image, the rim is blended with white and
                # pixels the ring barely touches stay transparent.
                if outer[n] < 0.25:
                    continue
                colour = mix(ring, mix(fill, dot_colour, dot[n]), inner[n])
                out.putpixel((n % size, n // size), mix((255, 255, 255), colour, outer[n]))
            result.append(out)
        save(result, "radio", dpi)


def check_boxes():
    """Check boxes for 144 DPI, the only step the theme has none for.

    Its NORMAL_CHECKBOX16 and NORMAL_CHECKBOX25 bitmaps serve 120 and 192 DPI.
    """
    if 144 not in DPIS:
        return
    states = load("CHECKBOX16", 12)
    size, supersample = 20, 8
    scale = size / states[0].width
    big = size * supersample
    stroke = Image.new("L", (big, big), 0)
    points = [(x * scale * supersample, y * scale * supersample)
              for x, y in ((3, 8), (6.5, 11.5), (13, 5))]
    ImageDraw.Draw(stroke).line(points, fill=255, width=round(1.8 * scale * supersample),
                                joint="curve")
    check = [v / 255 for v in stroke.resize((size, size), Image.BOX).getdata()]
    result = []
    for i, state in enumerate(states):
        border, fill = state.getpixel((0, 0)), state.getpixel((2, 2))
        width = 2 if state.getpixel((1, 1)) == border else 1
        out = Image.new("RGB", (size, size), border)
        draw = ImageDraw.Draw(out)
        draw.rectangle((width, width, size - 1 - width, size - 1 - width), fill=fill)
        if 4 <= i < 8:
            colour = state.getpixel((12, 5))
            for n in range(size * size):
                x, y = n % size, n // size
                if width <= x < size - width and width <= y < size - width:
                    out.putpixel((x, y), mix(fill, colour, check[n]))
        elif i >= 8:
            inset = round(3 * scale)
            draw.rectangle((inset, inset, size - 1 - inset, size - 1 - inset),
                           fill=state.getpixel((8, 8)))
        result.append(out)
    save(result, "checkbox", 144)


def main():
    scroll_arrows()
    arrow_glyphs("COMBOBUTTONGLYPH", 4, "down", "combo-glyph")
    arrow_glyphs("SPINUPGLYPH", 4, "up", "spin-up-glyph")
    arrow_glyphs("SPINDOWNGLYPH", 4, "down", "spin-down-glyph")
    arrow_glyphs("SPINLEFTGLYPH", 4, "left", "spin-left-glyph")
    arrow_glyphs("SPINRIGHTGLYPH", 4, "right", "spin-right-glyph")
    arrow_glyphs("TOOLBARBUTTONSSPLITDROPDOWNGLYPH", 6, "down", "split-dropdown-glyph")
    tree_glyphs()
    chevrons()
    resize_grips()
    radio_buttons()
    check_boxes()


if __name__ == "__main__":
    main()
