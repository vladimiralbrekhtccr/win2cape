#!/usr/bin/env python3
"""
win2cape - convert a Windows cursor pack (.ani / .cur) into a macOS Mousecape .cape

    python3 ani2cape.py /path/to/cursor-folder -o MyTheme.cape --name "My Theme"

Why this exists
---------------
Two things make this less trivial than it looks:

1. Pillow does NOT apply the 1-bpp AND mask stored in .cur/.ani frames. Every pixel
   decodes opaque, so cursors render as white boxes. We decode the DIB by hand.

2. On macOS 26 (Tahoe) the primary pointer is rendered via the identifiers
   `com.apple.coregraphics.ArrowS` / `.IBeamS`. Mousecape's own identifier list
   (last released 2020) doesn't include them, so replacing `.Arrow` silently no-ops.
   We emit both the classic and the S-variant identifiers.

Requires: Pillow  (pip install Pillow)
"""

import argparse
import io
import os
import plistlib
import struct
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required:  pip install Pillow")


# --------------------------------------------------------------------------
# Windows cursor decoding
# --------------------------------------------------------------------------

def parse_ani(data):
    """Parse a RIFF/ACON animated cursor. Returns (anih, [icon blobs], rates, seq)."""
    if data[:4] != b"RIFF" or data[8:12] != b"ACON":
        raise ValueError("not an ANI file")
    state = {"anih": None, "frames": [], "rates": None, "seq": None}

    def walk(buf, off, end):
        while off + 8 <= end:
            cid = buf[off:off + 4]
            size = struct.unpack("<I", buf[off + 4:off + 8])[0]
            body = off + 8
            if cid == b"LIST":
                walk(buf, body + 4, body + size)
            elif cid == b"anih":
                state["anih"] = struct.unpack("<9I", buf[body:body + 36])
            elif cid == b"icon":
                state["frames"].append(buf[body:body + size])
            elif cid == b"rate":
                state["rates"] = list(struct.unpack("<%dI" % (size // 4), buf[body:body + size]))
            elif cid == b"seq ":
                state["seq"] = list(struct.unpack("<%dI" % (size // 4), buf[body:body + size]))
            off = body + size + (size & 1)   # chunks are word-aligned

    walk(data, 12, len(data))
    return state["anih"], state["frames"], state["rates"], state["seq"]


def decode_icon(blob, index=0):
    """Decode one .cur/.ico image into (RGBA Image, hotspot_x, hotspot_y).

    Applies the 1-bpp AND transparency mask, which Pillow ignores.
    """
    _reserved, _type, _count = struct.unpack("<HHH", blob[:6])
    entry = 6 + index * 16
    hx, hy = struct.unpack("<HH", blob[entry + 4:entry + 8])
    size, offset = struct.unpack("<II", blob[entry + 8:entry + 16])
    dib = blob[offset:offset + size]

    if dib[:8] == b"\x89PNG\r\n\x1a\n":            # Vista+ PNG-compressed icon
        return Image.open(io.BytesIO(dib)).convert("RGBA"), hx, hy

    bi_size, bi_w, bi_h, _planes, bpp, _comp = struct.unpack("<IiiHHI", dib[:20])
    height = bi_h // 2                             # biHeight covers XOR + AND stacked
    ncolors = struct.unpack("<I", dib[32:36])[0] or (1 << bpp if bpp <= 8 else 0)

    palette = []
    for i in range(ncolors):
        b, g, r, _a = dib[bi_size + i * 4: bi_size + i * 4 + 4]
        palette.append((r, g, b))

    xor_off = bi_size + ncolors * 4
    row_bytes = ((bi_w * bpp + 31) // 32) * 4      # rows padded to 4 bytes
    mask_row = ((bi_w + 31) // 32) * 4
    and_off = xor_off + row_bytes * height

    img = Image.new("RGBA", (bi_w, height))
    px = img.load()
    for y in range(height):
        sy = height - 1 - y                        # DIB rows are bottom-up
        row = xor_off + sy * row_bytes
        mask = and_off + sy * mask_row
        for x in range(bi_w):
            a = 255
            if bpp == 8:
                r, g, b = palette[dib[row + x]]
            elif bpp == 4:
                byte = dib[row + x // 2]
                r, g, b = palette[(byte >> 4) if x % 2 == 0 else (byte & 0xF)]
            elif bpp == 1:
                r, g, b = palette[(dib[row + x // 8] >> (7 - x % 8)) & 1]
            elif bpp == 24:
                o = row + x * 3
                b, g, r = dib[o], dib[o + 1], dib[o + 2]
            elif bpp == 32:
                o = row + x * 4
                b, g, r, a = dib[o], dib[o + 1], dib[o + 2], dib[o + 3]
            else:
                raise ValueError("unsupported bit depth: %d" % bpp)
            if dib[mask + x // 8] >> (7 - x % 8) & 1:   # mask bit set => transparent
                a = 0
            px[x, y] = (r, g, b, a)
    return img, hx, hy


# --------------------------------------------------------------------------
# Windows role -> macOS cursor identifiers
#
# Identifiers taken from Mousecape's cursorMap() in mousecloak/MCDefs.m, plus the
# macOS 26 S-variants found by grepping the dyld shared cache (see README).
# --------------------------------------------------------------------------

ROLE_IDS = {
    "normal":      ["com.apple.coregraphics.Arrow", "com.apple.coregraphics.ArrowS"],
    "help":        ["com.apple.cursor.40"],
    "working":     ["com.apple.cursor.14", "com.apple.cursor.15", "com.apple.cursor.16"],
    "busy":        ["com.apple.coregraphics.Wait", "com.apple.cursor.4"],
    "precision":   ["com.apple.cursor.7", "com.apple.cursor.8",
                    "com.apple.cursor.41", "com.apple.cursor.20"],
    "text":        ["com.apple.coregraphics.IBeam", "com.apple.coregraphics.IBeamS",
                    "com.apple.coregraphics.IBeamXOR", "com.apple.cursor.26"],
    "unavailable": ["com.apple.cursor.3"],
    "vertical":    ["com.apple.cursor.23", "com.apple.cursor.32", "com.apple.cursor.21",
                    "com.apple.cursor.22", "com.apple.cursor.31", "com.apple.cursor.36"],
    "horizontal":  ["com.apple.cursor.19", "com.apple.cursor.28", "com.apple.cursor.17",
                    "com.apple.cursor.18", "com.apple.cursor.38", "com.apple.cursor.27"],
    "diagonal1":   ["com.apple.cursor.34", "com.apple.cursor.33", "com.apple.cursor.35"],
    "diagonal2":   ["com.apple.cursor.30", "com.apple.cursor.29", "com.apple.cursor.37"],
    "move":        ["com.apple.coregraphics.Move", "com.apple.cursor.11", "com.apple.cursor.12"],
    "alternate":   ["com.apple.coregraphics.ArrowCtx", "com.apple.cursor.24"],
    "link":        ["com.apple.cursor.2", "com.apple.cursor.13"],
    # macOS has no direct counterpart for these three Windows roles, so they are
    # repurposed onto real macOS cursors that would otherwise keep stock Apple art.
    # This is a judgement call - comment them out if you would rather skip them.
    "handwriting": ["com.apple.coregraphics.Copy", "com.apple.cursor.5"],   # Option-drag
    "person":      ["com.apple.coregraphics.Alias"],                        # Cmd+Option-drag
    "pin":         ["com.apple.cursor.25"],                                 # Poof (drag off Dock)
}

# Common filename spellings across Windows cursor packs.
ALIASES = {
    "normal": "normal", "pointer": "normal", "arrow": "normal", "default": "normal",
    "help": "help",
    "working": "working", "appstarting": "working",
    "busy": "busy", "wait": "busy",
    "precision": "precision", "crosshair": "precision", "cross": "precision",
    "text": "text", "ibeam": "text",
    "unavailable": "unavailable", "no": "unavailable", "forbidden": "unavailable",
    "vertical": "vertical", "sizens": "vertical", "ns": "vertical",
    "horizontal": "horizontal", "sizewe": "horizontal", "we": "horizontal",
    "diagonal1": "diagonal1", "sizenwse": "diagonal1", "nwse": "diagonal1",
    "diagonal2": "diagonal2", "sizenesw": "diagonal2", "nesw": "diagonal2",
    "move": "move", "sizeall": "move",
    "alternate": "alternate", "uparrow": "alternate", "up": "alternate",
    "link": "link", "hand": "link",
    "handwriting": "handwriting", "nwpen": "handwriting", "pen": "handwriting",
    "person": "person",
    "pin": "pin",
}


def role_for(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    key = "".join(ch for ch in stem.lower() if ch.isalnum())
    return ALIASES.get(key)


# --------------------------------------------------------------------------
# Cape building
# --------------------------------------------------------------------------

def to_png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def build_entry(path, scales=(1, 2)):
    """Build one Mousecape cursor entry from a .ani or .cur file."""
    if path.lower().endswith(".ani"):
        anih, frames, _rates, _seq = parse_ani(open(path, "rb").read())
        images, hx, hy = [], 0, 0
        for blob in frames:
            img, hx, hy = decode_icon(blob)
            images.append(img)
        duration = (anih[7] or 6) / 60.0        # anih rate is in 1/60s jiffies
    else:
        img, hx, hy = decode_icon(open(path, "rb").read())
        images, duration = [img], 1.0

    w, h = images[0].size
    reps = []
    for scale in scales:
        strip = Image.new("RGBA", (w * scale, h * len(images) * scale), (0, 0, 0, 0))
        for i, img in enumerate(images):
            frame = img if scale == 1 else img.resize((w * scale, h * scale), Image.NEAREST)
            strip.paste(frame, (0, i * h * scale))
        reps.append(to_png(strip))

    return {
        "FrameCount": len(images),
        "FrameDuration": float(duration),
        "HotSpotX": float(hx),
        "HotSpotY": float(hy),
        "PointsWide": float(w),
        "PointsHigh": float(h),
        "Representations": reps,
    }


def build_cape(folder, name, author, identifier):
    cursors, mapped, skipped = {}, [], []
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith((".ani", ".cur")):
            continue
        role = role_for(fn)
        if role is None or role not in ROLE_IDS:
            skipped.append(fn)
            continue
        entry = build_entry(os.path.join(folder, fn))
        for cid in ROLE_IDS[role]:
            cursors[cid] = dict(entry)
        mapped.append((fn, role, len(ROLE_IDS[role]), entry["FrameCount"]))

    cape = {
        "Author": author,
        "CapeName": name,
        "CapeVersion": 1.0,
        "Cursors": cursors,
        "HiDPI": True,
        "Identifier": identifier,
        "MinimumVersion": 2.0,
        "Version": 1.0,
    }
    return cape, mapped, skipped


def main():
    ap = argparse.ArgumentParser(description="Convert Windows .ani/.cur cursors to a macOS .cape")
    ap.add_argument("folder", help="folder containing .ani / .cur files")
    ap.add_argument("-o", "--output", default=None, help="output .cape path")
    ap.add_argument("--name", default=None, help="cape name shown in Mousecape")
    ap.add_argument("--author", default="Converted with win2cape", help="cape author field")
    ap.add_argument("--identifier", default=None, help="reverse-DNS cape identifier")
    args = ap.parse_args()

    name = args.name or os.path.basename(os.path.abspath(args.folder))
    slug = "".join(ch for ch in name.lower() if ch.isalnum()) or "cape"
    identifier = args.identifier or ("com.win2cape." + slug)
    output = args.output or (name + ".cape")

    cape, mapped, skipped = build_cape(args.folder, name, args.author, identifier)
    if not cape["Cursors"]:
        sys.exit("No recognisable cursor files found in %s" % args.folder)

    for fn, role, n_ids, frames in mapped:
        print("  %-20s -> %-12s %2d id(s)  %d frame(s)" % (fn, role, n_ids, frames))
    if skipped:
        print("  skipped (no macOS equivalent): %s" % ", ".join(skipped))

    with open(output, "wb") as fh:
        plistlib.dump(cape, fh)
    print("\nWrote %s - %d cursor identifiers, %.0f KB"
          % (output, len(cape["Cursors"]), os.path.getsize(output) / 1024))
    print("Apply with:  mousecloak --apply %s" % output)


if __name__ == "__main__":
    main()
