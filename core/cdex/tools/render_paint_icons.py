#!/usr/bin/env python3
"""Render the high-DPI tool icons of Paint in artwork/.

The 96 DPI strip (src/base/applications/mspaint/img/iconbar.bmp) is 16 pixel
art with no vector source, so the sixteen tools are redrawn here as vector
shapes after it, on a 16 unit grid, and rendered at 16 pixels times the scale.
The strips are 32-bit bitmaps with an alpha channel.

Needs Pillow (python3-pil).

Usage: render_paint_icons.py <dpi>...
"""
import math
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "artwork")
DPIS = [int(arg) for arg in sys.argv[1:]]
SUPERSAMPLE = 8

NAVY = (22, 45, 84)
OUTLINE = (40, 62, 98)
PALE = (238, 244, 251)
SKY = (150, 190, 240)
# Fill of the closed shapes: a gradient from the top left to the bottom right.
SHAPE_FILL = (PALE, SKY, (3, 3), (13, 13))


class Canvas:
    """A 16x16 unit drawing surface, rendered larger and scaled down for smooth edges."""

    def __init__(self, size):
        self.scale = size * SUPERSAMPLE / 16
        self.size = size
        self.image = Image.new("RGBA", (size * SUPERSAMPLE,) * 2, (0, 0, 0, 0))

    def _points(self, points):
        return [(x * self.scale, y * self.scale) for x, y in points]

    def _paint(self, mask, fill):
        """Fill the masked area with a colour or a (start colour, end colour, start, end) gradient."""
        if len(fill) == 3:
            layer = Image.new("RGBA", self.image.size, fill + (255,))
        else:
            first, second, (x0, y0), (x1, y1) = fill
            length = (x1 - x0) ** 2 + (y1 - y0) ** 2
            width = self.image.width
            ramp = Image.new("L", self.image.size)
            # Position of every pixel along the gradient axis, 0..255.
            ramp.putdata([
                max(0, min(255, round(255 * (((x / self.scale - x0) * (x1 - x0)
                                              + (y / self.scale - y0) * (y1 - y0)) / length))))
                for y in range(width) for x in range(width)])
            layer = Image.composite(Image.new("RGBA", self.image.size, second + (255,)),
                                    Image.new("RGBA", self.image.size, first + (255,)), ramp)
        self.image.paste(layer, (0, 0), mask)

    def polygon(self, points, fill):
        mask = Image.new("L", self.image.size, 0)
        ImageDraw.Draw(mask).polygon(self._points(points), fill=255)
        self._paint(mask, fill)

    def cut(self, points):
        """Make a polygon transparent."""
        mask = Image.new("L", self.image.size, 0)
        ImageDraw.Draw(mask).polygon(self._points(points), fill=255)
        self.image.paste((0, 0, 0, 0), (0, 0), mask)

    def ellipse(self, box, fill):
        mask = Image.new("L", self.image.size, 0)
        ImageDraw.Draw(mask).ellipse([v * self.scale for v in box], fill=255)
        self._paint(mask, fill)

    def line(self, points, fill, width, closed=False):
        """A stroke with round joints and ends."""
        mask = Image.new("L", self.image.size, 0)
        draw = ImageDraw.Draw(mask)
        points = self._points(points + points[:1] if closed else points)
        radius = width * self.scale / 2
        draw.line(points, fill=255, width=round(width * self.scale), joint="curve")
        for x, y in points:
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
        self._paint(mask, fill)

    def dashes(self, points, fill, width, dash, gap):
        """A dashed closed outline."""
        points = points + points[:1]
        position, drawing = 0.0, True
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            length = math.hypot(x1 - x0, y1 - y0)
            start = 0.0
            while start < length:
                step = min((dash if drawing else gap) - position, length - start)
                if drawing:
                    a, b = start / length, (start + step) / length
                    self.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a),
                               (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)], fill, width)
                start += step
                position += step
                if position >= (dash if drawing else gap) - 1e-9:
                    position, drawing = 0.0, not drawing

    def render(self):
        # Average premultiplied pixels, or transparent ones would tint the edges.
        return self.image.convert("RGBa").resize((self.size, self.size), Image.BOX).convert("RGBA")


def bar(c, start, end, width, fill):
    """A straight bar with square ends from start to end."""
    (x0, y0), (x1, y1) = start, end
    length = math.hypot(x1 - x0, y1 - y0)
    nx, ny = (y0 - y1) / length * width / 2, (x1 - x0) / length * width / 2
    c.polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], fill)


def selection(c, points):
    c.line(points, (255, 255, 255), 2.2, closed=True)
    c.dashes(points, NAVY, 1.0, 1.7, 1.1)


def free_select(c):
    selection(c, [(2.2, 6.2), (3.2, 2.6), (8.4, 1.6), (10.6, 5.0), (14.2, 7.4), (14.0, 12.0),
                  (9.0, 14.2), (3.4, 13.4), (1.8, 10.0)])


def rect_select(c):
    selection(c, [(1.8, 2.8), (14.2, 2.8), (14.2, 13.2), (1.8, 13.2)])


def eraser(c):
    c.polygon([(0.8, 9.2), (8.6, 1.4), (14.4, 1.4), (14.4, 6.2), (6.6, 14.0), (0.8, 14.0)],
              (132, 110, 28))
    c.polygon([(1.6, 9.5), (9.0, 2.2), (13.6, 2.2), (6.3, 9.5)], ((246, 232, 122), (214, 190, 70), (2, 2), (12, 9)))
    c.polygon([(1.6, 10.3), (6.0, 10.3), (6.0, 13.2), (1.6, 13.2)], (240, 222, 104))
    c.polygon([(6.8, 10.0), (13.6, 3.2), (13.6, 5.8), (6.8, 12.8)], (176, 150, 44))


def fill(c):
    c.polygon([(6.4, 6.0), (4.0, 6.6), (3.0, 8.6), (3.2, 12.6), (5.0, 12.6), (5.0, 9.6), (6.6, 8.4)],
              ((214, 178, 60), (150, 118, 26), (3, 6), (6, 12)))
    c.polygon([(11.0, 3.2), (15.6, 8.6), (11.0, 14.8), (6.0, 8.6)], OUTLINE)
    c.polygon([(11.0, 4.6), (14.4, 8.6), (11.0, 13.2), (7.3, 8.6)],
              (PALE, (120, 160, 214), (8, 5), (13, 13)))
    c.line([(11.0, 0.8), (11.0, 8.4)], (74, 118, 190), 1.0)
    c.ellipse((10.2, 7.6, 11.8, 9.2), OUTLINE)


def picker(c):
    bar(c, (1.4, 14.6), (8.4, 7.6), 3.0, (128, 138, 150))
    bar(c, (2.0, 14.0), (8.0, 8.0), 1.6, (PALE, (190, 208, 230), (2, 14), (8, 8)))
    bar(c, (6.6, 9.4), (11.4, 4.6), 4.2, (58, 70, 88))
    bar(c, (9.2, 6.8), (13.4, 2.6), 3.2, ((150, 186, 226), (40, 100, 168), (9, 3), (13, 6)))
    c.ellipse((11.0, 0.8, 15.2, 5.0), ((150, 186, 226), (40, 100, 168), (11.5, 1), (15, 5)))


def zoom(c):
    bar(c, (9.8, 9.8), (14.6, 14.6), 3.0, (132, 132, 136))
    bar(c, (10.4, 10.4), (14.0, 14.0), 1.6, (206, 206, 210))
    c.ellipse((0.8, 0.8, 12.2, 12.2), (140, 154, 174))
    c.ellipse((2.2, 2.2, 10.8, 10.8), ((244, 248, 253), (176, 200, 232), (3, 3), (10, 10)))


def pencil(c):
    bar(c, (3.2, 12.8), (12.0, 4.0), 3.6, (120, 76, 22))
    bar(c, (3.2, 12.8), (12.0, 4.0), 2.4, ((240, 180, 84), (196, 128, 44), (4, 4), (9, 9)))
    c.polygon([(0.8, 15.2), (1.6, 11.6), (4.4, 14.4)], (232, 204, 164))
    c.polygon([(0.8, 15.2), (1.1, 13.8), (2.2, 14.9)], (60, 48, 40))
    bar(c, (11.4, 4.6), (12.8, 3.2), 3.6, (176, 176, 180))
    bar(c, (12.6, 3.4), (14.4, 1.6), 3.6, (150, 30, 24))
    bar(c, (12.9, 3.1), (14.1, 1.9), 2.4, (232, 64, 50))


def brush(c):
    c.polygon([(0.8, 15.2), (2.2, 10.6), (5.4, 13.8)], ((70, 70, 74), (16, 16, 18), (2, 11), (3, 15)))
    bar(c, (3.6, 12.4), (8.4, 7.6), 3.8, (96, 96, 100))
    bar(c, (4.0, 12.0), (8.0, 8.0), 2.6, ((240, 240, 244), (160, 160, 168), (4, 8), (8, 12)))
    bar(c, (7.6, 8.4), (14.2, 1.8), 3.0, (124, 90, 56))
    bar(c, (8.2, 7.8), (13.8, 2.2), 1.8, ((236, 204, 164), (190, 146, 100), (9, 2), (13, 7)))


def airbrush(c):
    for x, y, colour in ((1.4, 3.0, (236, 40, 36)), (2.6, 4.2, (250, 130, 20)), (1.2, 5.6, (250, 220, 20)),
                         (2.6, 7.2, (240, 200, 30)), (1.4, 8.8, (120, 190, 50)),
                         (2.4, 10.6, (150, 150, 160)), (1.6, 12.6, (60, 90, 220)),
                         (3.6, 2.2, (200, 40, 40)), (3.4, 5.8, (250, 160, 30))):
        c.ellipse((x - 0.6, y - 0.6, x + 0.6, y + 0.6), colour)
    bar(c, (4.4, 2.6), (6.0, 4.2), 1.8, (150, 150, 156))
    bar(c, (5.2, 3.8), (13.0, 12.6), 5.4, (30, 40, 60))
    bar(c, (5.8, 4.5), (12.4, 11.9), 4.0, (PALE, (70, 140, 226), (11, 6), (7, 11)))


def text(c):
    shape = [(6.4, 1.6), (9.6, 1.6), (14.8, 14.4), (11.6, 14.4), (10.5, 11.4), (5.5, 11.4),
             (4.4, 14.4), (1.2, 14.4)]
    c.polygon(shape, (36, 76, 140))
    inner = [(7.0, 2.6), (9.0, 2.6), (13.4, 13.4), (12.3, 13.4), (11.2, 10.4), (4.8, 10.4),
             (3.7, 13.4), (2.6, 13.4)]
    c.polygon(inner, ((170, 198, 236), (60, 110, 186), (8, 2), (8, 14)))
    c.polygon([(8.0, 4.8), (9.8, 9.0), (6.2, 9.0)], (36, 76, 140))
    # The counter of the letter.
    c.cut([(8.0, 6.6), (8.7, 8.3), (7.3, 8.3)])


def line(c):
    c.line([(1.6, 1.6), (14.4, 14.4)], (150, 150, 154), 1.9)
    c.line([(1.6, 1.6), (14.4, 14.4)], (44, 44, 48), 1.0)


def curve(c):
    p0, p1, p2, p3 = (9.4, 1.0), (16.0, 5.6), (0.6, 9.0), (8.0, 15.0)
    points = []
    for i in range(41):
        t = i / 40
        points.append(tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t ** 2 * d
                            + t ** 3 * e for a, b, d, e in zip(p0, p1, p2, p3)))
    c.line(points, (150, 150, 154), 1.9)
    c.line(points, (36, 36, 40), 1.0)


def rect(c):
    c.polygon([(1.2, 2.8), (14.8, 2.8), (14.8, 13.2), (1.2, 13.2)], OUTLINE)
    c.polygon([(2.2, 3.8), (13.8, 3.8), (13.8, 12.2), (2.2, 12.2)], SHAPE_FILL)


def polygon(c):
    c.line([(4.8, 3.2), (9.6, 3.2), (8.4, 7.6), (14.2, 7.6), (14.2, 12.8), (1.8, 12.8)], OUTLINE, 1.2,
           closed=True)
    c.polygon([(5.4, 4.0), (8.6, 4.0), (7.4, 8.4), (13.4, 8.4), (13.4, 12.0), (3.0, 12.0)], SHAPE_FILL)


def ellipse(c):
    c.ellipse((1.0, 3.2, 15.0, 12.8), OUTLINE)
    c.ellipse((2.0, 4.2, 14.0, 11.8), SHAPE_FILL)


def rounded_rect(c):
    c.line([(3.0, 4.6), (13.0, 4.6), (13.0, 11.4), (3.0, 11.4)], OUTLINE, 3.6, closed=True)
    c.polygon([(3.0, 4.6), (13.0, 4.6), (13.0, 11.4), (3.0, 11.4)], OUTLINE)
    c.line([(3.4, 5.0), (12.6, 5.0), (12.6, 11.0), (3.4, 11.0)], SHAPE_FILL, 2.2, closed=True)
    c.polygon([(3.4, 5.0), (12.6, 5.0), (12.6, 11.0), (3.4, 11.0)], SHAPE_FILL)


# In the order of the tool box buttons.
TOOLS = (free_select, rect_select, eraser, fill, picker, zoom, pencil, brush, airbrush, text,
         line, curve, rect, polygon, ellipse, rounded_rect)


def main():
    for dpi in DPIS:
        size = round(16 * dpi / 96)
        strip = Image.new("RGBA", (size * len(TOOLS), size), (0, 0, 0, 0))
        for i, tool in enumerate(TOOLS):
            canvas = Canvas(size)
            tool(canvas)
            strip.paste(canvas.render(), (i * size, 0))
        strip.save(os.path.join(OUT, f"mspaint-tools-{dpi}.bmp"))


if __name__ == "__main__":
    main()
