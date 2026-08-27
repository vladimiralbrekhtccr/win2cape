#!/usr/bin/env python3
"""
Regenerates the README diagrams. All artwork here is original and synthetic -
the demo cursor is drawn from scratch below, so no third-party art is used.

    python3 docs/make-diagrams.py
"""
import os
from PIL import Image, ImageDraw

OUT = os.path.dirname(os.path.abspath(__file__))
N = 20                      # demo cursor grid size
INK, FILL = (26, 26, 32), (255, 255, 255)

# Palette chosen to stay legible on both light and dark GitHub themes.
CARD, EDGE, TEXT, MUTED = "#ffffff", "#d6dae1", "#1f2328", "#6a737d"
ACCENT, GOOD, BAD = "#7e52bc", "#1a7f37", "#cf222e"


def demo_cursor():
    """Draw a classic arrow: white fill, dark outline, on a transparent field."""
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    poly = [(2, 1), (2, 15), (5.5, 11.5), (8, 17), (10.5, 16), (8, 10.5), (13, 10.5)]
    d.polygon(poly, fill=FILL, outline=INK)
    return img


def cells(img):
    px = img.load()
    return [[px[x, y] for x in range(N)] for y in range(N)]


def grid_svg(rows, x0, y0, cell, mode):
    """Emit one pixel grid. mode: 'opaque' | 'mask' | 'alpha'.

    Each grid sits on a grey backing so that an opaque white field reads as a
    solid box, while genuine transparency lets the backing show through.
    """
    out = ['<rect x="%g" y="%g" width="%g" height="%g" fill="#e4e7ec"/>'
           % (x0, y0, N * cell, N * cell)]
    for y, row in enumerate(rows):
        for x, (r, g, b, a) in enumerate(row):
            px, py = x0 + x * cell, y0 + y * cell
            if mode == "mask":
                col = "#1f2328" if a > 127 else "#ffffff"
            elif mode == "opaque":
                col = "#%02x%02x%02x" % (r, g, b) if a > 127 else "#ffffff"
            else:
                if a <= 127:
                    col = "#eef0f3" if (x + y) % 2 == 0 else "#dfe3e8"
                else:
                    col = "#%02x%02x%02x" % (r, g, b)
            out.append('<rect x="%g" y="%g" width="%g" height="%g" fill="%s"/>'
                       % (px, py, cell, cell, col))
    out.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="%s"/>'
               % (x0, y0, N * cell, N * cell, EDGE))
    return "".join(out)


def text(x, y, s, size=13, fill=TEXT, weight="600", anchor="middle"):
    return ('<text x="%g" y="%g" font-family="ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial"'
            ' font-size="%g" font-weight="%s" fill="%s" text-anchor="%s">%s</text>'
            % (x, y, size, weight, fill, anchor, s))


def mask_diagram():
    cur = demo_cursor()
    rows = cells(cur)
    cell, gap = 9, 58
    grid = N * cell
    W, H = 2 * 30 + 3 * grid + 2 * gap, 306
    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
         % (W, H, W, H)]
    p.append('<rect width="%d" height="%d" rx="10" fill="%s" stroke="%s"/>' % (W, H, CARD, EDGE))
    p.append(text(W / 2, 30, "Windows cursors store transparency in a separate 1-bpp AND mask", 13))
    p.append(text(W / 2, 50, "Pillow does not apply it — so every pixel decodes opaque", 12, MUTED, "400"))

    panels = [("XOR (colour) data", "opaque", BAD, "Pillow stops here: a white box"),
              ("AND mask (1-bpp)", "mask", MUTED, "white = bit 1 = cut out"),
              ("Correct result", "alpha", GOOD, "mask applied → transparent")]
    for i, (label, mode, col, sub) in enumerate(panels):
        x0 = 30 + i * (grid + gap)
        p.append(grid_svg(rows, x0, 80, cell, mode))
        p.append(text(x0 + N * cell / 2, 285, label, 12, col))
        p.append(text(x0 + N * cell / 2, 272, sub, 10, MUTED, "400"))
        if i < 2:
            ax = x0 + N * cell + gap / 2
            p.append('<path d="M%g 175 L%g 175" stroke="%s" stroke-width="2" marker-end="url(#a)"/>'
                     % (ax - 16, ax + 10, MUTED))
    p.append('<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6"'
             ' markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="%s"/></marker></defs>' % MUTED)
    p.append("</svg>")
    open(os.path.join(OUT, "mask-bug.svg"), "w").write("".join(p))


def pipeline_diagram():
    W, H = 820, 190
    box_w, box_h, y = 132, 58, 66
    steps = [("Windows pack", ".ani / .cur"), ("RIFF parse", "frames + rate"),
             ("DIB decode", "+ AND mask"), ("Frame strip", "1x and 2x PNG"),
             ("cape plist", "42 identifiers")]
    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
         % (W, H, W, H)]
    p.append('<rect width="%d" height="%d" rx="10" fill="%s" stroke="%s"/>' % (W, H, CARD, EDGE))
    p.append(text(W / 2, 30, "win2cape conversion pipeline", 14))
    gap = (W - 60 - len(steps) * box_w) / (len(steps) - 1)
    for i, (title, sub) in enumerate(steps):
        x = 30 + i * (box_w + gap)
        last = i == len(steps) - 1
        p.append('<rect x="%g" y="%g" width="%g" height="%g" rx="7" fill="%s" stroke="%s" stroke-width="%s"/>'
                 % (x, y, box_w, box_h, "#faf7fe" if last else "#f6f8fa", ACCENT if last else EDGE,
                    "1.6" if last else "1"))
        p.append(text(x + box_w / 2, y + 24, title, 12, ACCENT if last else TEXT))
        p.append(text(x + box_w / 2, y + 42, sub, 10, MUTED, "400"))
        if not last:
            ax = x + box_w
            p.append('<path d="M%g %g L%g %g" stroke="%s" stroke-width="2" marker-end="url(#b)"/>'
                     % (ax + 6, y + box_h / 2, ax + gap - 8, y + box_h / 2, MUTED))
    p.append(text(W / 2, 168, "macOS 26 needs com.apple.coregraphics.ArrowS — not .Arrow — for the main pointer",
                  11, ACCENT, "600"))
    p.append('<defs><marker id="b" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6"'
             ' markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="%s"/></marker></defs>' % MUTED)
    p.append("</svg>")
    open(os.path.join(OUT, "pipeline.svg"), "w").write("".join(p))


if __name__ == "__main__":
    mask_diagram()
    pipeline_diagram()
    print("wrote mask-bug.svg and pipeline.svg")
