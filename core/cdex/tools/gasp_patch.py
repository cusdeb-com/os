#!/usr/bin/env python3
"""Rewrite the GASP table of a TTF font to 'smooth + gridfit at all sizes'.

The GASP table tells the rasterizer, per pixel size (PPEM), whether to
gridfit and/or antialias. We replace all ranges with a single one:
    { rangeMaxPPEM: 0xFFFF, rangeGaspBehavior: 0x0003 }
behavior bits: 1 = GASP_GRIDFIT, 2 = GASP_DOGRAY (grayscale smoothing).

Usage: gasp_patch.py <in.ttf> <out.ttf>
"""
import struct
import sys


def checksum(data):
    # TTF table checksum: big-endian uint32 sum, padded to 4 bytes
    if len(data) % 4:
        data += b"\0" * (4 - len(data) % 4)
    return sum(struct.unpack(">%dI" % (len(data) // 4), data)) & 0xFFFFFFFF


def gasp_patch(src, dst):
    data = bytearray(open(src, "rb").read())
    num_tables = struct.unpack(">H", data[4:6])[0]

    head_off = gasp_off = gasp_rec = None
    for i in range(num_tables):
        rec = 12 + i * 16
        tag = bytes(data[rec:rec + 4])
        off = struct.unpack(">I", data[rec + 8:rec + 12])[0]
        if tag == b"gasp":
            gasp_off, gasp_rec = off, rec
        elif tag == b"head":
            head_off = off

    if gasp_rec is None:
        raise SystemExit(f"{src}: no gasp table")
    if head_off is None:
        raise SystemExit(f"{src}: no head table")

    old_len = struct.unpack(">I", data[gasp_rec + 12:gasp_rec + 16])[0]

    # new gasp: version 0, numRanges 1, single record {0xFFFF, 0x0003}
    new_gasp = struct.pack(">HHHH", 0, 1, 0xFFFF, 0x0003)
    if len(new_gasp) > old_len:
        raise SystemExit(f"{src}: gasp table too small ({old_len} bytes)")
    data[gasp_off:gasp_off + len(new_gasp)] = new_gasp

    # shrink the table in the directory and fix its checksum; bytes past
    # the new length are dead weight and ignored by parsers
    struct.pack_into(">I", data, gasp_rec + 12, len(new_gasp))
    struct.pack_into(">I", data, gasp_rec + 4, checksum(bytes(data[gasp_off:gasp_off + len(new_gasp)])))

    # fix global checkSumAdjustment in head
    struct.pack_into(">I", data, head_off + 8, 0)
    struct.pack_into(">I", data, head_off + 8, (0xB1B0AFBA - checksum(bytes(data))) & 0xFFFFFFFF)

    open(dst, "wb").write(bytes(data))
    print("patched:", dst)


if __name__ == "__main__":
    gasp_patch(sys.argv[1], sys.argv[2])
