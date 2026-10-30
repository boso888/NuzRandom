"""Lector de textos del juego (formato GameFreak gen 7/8), para mostrar nombres reales.

Solo se usa para el registro de cambios y para aceptar nombres en los ajustes.
Si no se encuentra el archivo, se usan números.
"""
from __future__ import annotations

import struct
from pathlib import Path

LANGS = ("Spanish", "English")


def read_lines(data: bytes) -> list[str]:
    try:
        sections, count, _total, _key, sec_off = struct.unpack_from("<HHIII", data, 0)
        out = []
        for i in range(count):
            off, length = struct.unpack_from("<IH", data, sec_off + 4 + i * 8)
            key = (0x7C89 + 0x2983 * i) & 0xFFFF
            chars = []
            pos = sec_off + off
            k = 0
            words = []
            for j in range(length):
                w = struct.unpack_from("<H", data, pos + j * 2)[0] ^ key
                key = ((key << 3) | (key >> 13)) & 0xFFFF
                words.append(w)
            while k < len(words):
                w = words[k]
                if w == 0:
                    break
                if w == 0x10:  # código de control: [0x10, n, args...]
                    n = words[k + 1] if k + 1 < len(words) else 0
                    k += 2 + n
                    continue
                if w == 0xE07F:
                    chars.append(" ")
                elif w == 0xE08D:
                    chars.append("…")
                elif w == 0xE08E:
                    chars.append("♂")
                elif w == 0xE08F:
                    chars.append("♀")
                else:
                    chars.append(chr(w))
                k += 1
            out.append("".join(chars).strip())
        return out
    except (struct.error, IndexError):
        return []


def load_names(romfs: Path, filename: str) -> list[str]:
    base = Path(romfs) / "bin" / "message"
    for lang in LANGS:
        d = base / lang
        if not d.is_dir():
            continue
        for p in d.rglob(filename):
            lines = read_lines(p.read_bytes())
            if lines:
                return lines
    return []
