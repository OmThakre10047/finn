#!/usr/bin/env python3
import struct, zlib
from pathlib import Path

def png(width, height, pixel_fn):
    raw = b""
    for y in range(height):
        raw += b"\x00"
        for x in range(width):
            raw += bytes(pixel_fn(x, y))
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(raw, 9))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend

BG_DARK = (9, 9, 11, 255)
ACCENT = (52, 211, 153, 255)
FG = (244, 244, 245, 255)

# Simple "F" + dot mark, drawn as rectangles in a 16x16 grid, scaled to size
GRID = 16
F_PIXELS = set()
# vertical stem (2 wide) rows 3..12
for y in range(3, 13):
    for x in range(3, 5):
        F_PIXELS.add((x, y))
# top bar rows 3..5, cols 5..11
for y in range(3, 6):
    for x in range(5, 12):
        F_PIXELS.add((x, y))
# middle bar rows 7..8, cols 5..9
for y in range(7, 9):
    for x in range(5, 10):
        F_PIXELS.add((x, y))
DOT = {(13, 11), (13, 12), (12, 12)}

def make(size):
    s = size // GRID
    def px(x, y):
        gx, gy = x // s, y // s
        if (gx, gy) in DOT:
            return ACCENT
        if (gx, gy) in F_PIXELS:
            return FG
        return BG_DARK
    return png(size, size, px)

out = Path(__file__).resolve().parent.parent.parent / "frontend" / "public"
out.mkdir(parents=True, exist_ok=True)
for size in (192, 512):
    (out / f"icon-{size}.png").write_bytes(make(size))
    print("wrote icon", size)
