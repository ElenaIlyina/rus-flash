#!/usr/bin/env python3
"""Recover visible dictionary articles from the pinned PalmDOC MOBI7 copy.

Preparation only: no source HTML or JavaScript is executed. The synthetic idx
wrappers mark visible headword boundaries for extract_mobi_articles.py; they do
not claim to reproduce MOBI search-index metadata. Other MOBI profiles fail closed.
"""
import argparse
import html
from pathlib import Path
import re
import struct


def indexed_dictionary(path):
    raw = Path(path).read_bytes()
    if len(raw) < 300 or len(raw) > 64 * 1024 * 1024:
        raise ValueError("Unsupported dictionary size")
    u16 = lambda pos: struct.unpack_from(">H", raw, pos)[0]
    u32 = lambda pos: struct.unpack_from(">I", raw, pos)[0]
    count = u16(76)
    if not count or 78 + 8 * count > len(raw):
        raise ValueError("Invalid Palm record directory")
    offsets = [u32(78 + 8 * i) for i in range(count)] + [len(raw)]
    if offsets[0] < 78 + 8 * count or any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError("Invalid Palm record offsets")
    start = offsets[0]
    if offsets[1] - start < 244 or raw[start + 16:start + 20] != b"MOBI":
        raise ValueError("Missing MOBI7 header")
    if u16(start) != 2 or u32(start + 28) != 65001 or u32(start + 36) != 7:
        raise ValueError("Expected UTF-8 PalmDOC MOBI7")
    flags = u16(start + 242)
    records, length = u16(start + 8), u32(start + 4)
    if flags != 3 or not 0 < records < count or length > 64 * 1024 * 1024:
        raise ValueError("Unsupported MOBI7 text profile")

    def strip_trailing(data):
        trailing = 0
        for shift, byte in enumerate(reversed(data[-4:])):
            trailing |= (byte & 127) << (shift * 7)
            if byte & 128:
                break
        else:
            raise ValueError("Unterminated trailing-data length")
        if not 0 < trailing <= len(data):
            raise ValueError("Invalid trailing-data length")
        data = data[:-trailing]
        if not data or 1 + (data[-1] & 3) > len(data):
            raise ValueError("Invalid multibyte trailer")
        return data[:-(1 + (data[-1] & 3))]

    def decompress(data):
        out = bytearray()
        cursor = 0
        while cursor < len(data):
            byte = data[cursor]
            cursor += 1
            if 1 <= byte <= 8:
                if cursor + byte > len(data):
                    raise ValueError("Truncated literal run")
                out.extend(data[cursor:cursor + byte])
                cursor += byte
            elif byte < 128:
                out.append(byte)
            elif byte >= 192:
                out.extend((32, byte ^ 128))
            else:
                if cursor == len(data):
                    raise ValueError("Truncated backreference")
                value = (byte << 8) | data[cursor]
                cursor += 1
                distance, size = (value >> 3) & 2047, (value & 7) + 3
                if not 0 < distance <= len(out):
                    raise ValueError("Invalid PalmDOC backreference")
                for _ in range(size):
                    out.append(out[-distance])
            if len(out) > 4096:
                raise ValueError("Decoded text record exceeds profile limit")
        return bytes(out)

    text = b"".join(decompress(strip_trailing(raw[offsets[i]:offsets[i + 1]]))
                    for i in range(1, records + 1))
    if len(text) != length:
        raise ValueError("Decoded text length differs from MOBI header")
    decoded = text.decode("utf-8", errors="strict")
    wrapped = []
    for block in re.split(r'(?=<font size="6" color="#002984">)', decoded):
        match = re.search(r'<font size="6" color="#002984"><b>(.*?)</b></font>', block, re.S)
        if not match:
            continue
        headword = html.unescape(re.sub("<[^>]+>", "", match[1])).strip()
        if not headword:
            raise ValueError("Empty visible dictionary headword")
        wrapped.append('<idx:entry><idx:orth value="' + html.escape(headword, quote=True)
                       + '"></idx:orth>' + block + "</idx:entry>")
    if len(wrapped) != 40291:
        raise ValueError("Unexpected headword count in the inspected dictionary profile")
    return "".join(wrapped)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mobi_path")
    parser.add_argument("output_html")
    args = parser.parse_args()
    Path(args.output_html).write_text(indexed_dictionary(args.mobi_path), encoding="utf-8")


if __name__ == "__main__":
    main()
