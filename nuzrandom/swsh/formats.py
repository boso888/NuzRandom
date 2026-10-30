"""Formatos binarios de Espada/Escudo.

- GFPak (archivos .gfpak, compresión LZ4 tipo 2)
- FlatBuffers: solo se editan escalares que YA existen en el buffer, sin
  reconstruirlo. Así nunca se mueve un offset y el archivo sigue siendo válido.

Estructuras documentadas por la comunidad (pkNX) y verificadas por PokeFeur
Randomizer SWSH (GPLv3), del que este proyecto toma las disposiciones de datos.
"""
from __future__ import annotations

import struct

GFPAK_MAGIC = 0x4B434150584C4647


def fnv1a64(text: str) -> int:
    h = 0xCBF29CE484222645
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


# --------------------------------------------------------------------- LZ4 ---
def _lz4():
    try:
        import lz4.block  # type: ignore
        return lz4.block
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Falta el paquete 'lz4'. Ejecuta Iniciar.bat para instalar dependencias.") from exc


def lz4_decompress(data: bytes, size: int) -> bytes:
    return _lz4().decompress(data, uncompressed_size=size)


def lz4_compress(data: bytes) -> bytes:
    return _lz4().compress(data, store_size=False)


# ------------------------------------------------------------------- GFPak ---
class Gfpak:
    def __init__(self, raw: bytes):
        d = raw
        magic, self.version, self.reloc, n_files, n_folders = struct.unpack_from("<QIIii", d, 0)
        if magic != GFPAK_MAGIC:
            raise ValueError("No es un GFPak válido")
        ptr_table, ptr_hashes = struct.unpack_from("<qq", d, 24)
        folder_ptrs = [struct.unpack_from("<q", d, 40 + i * 8)[0] for i in range(n_folders)]
        self.hash_paths = [struct.unpack_from("<Q", d, ptr_hashes + i * 8)[0] for i in range(n_files)]
        self.folders = []
        for fp in folder_ptrs:
            fhash, count, pad = struct.unpack_from("<QiI", d, fp)
            files = [struct.unpack_from("<QiI", d, fp + 0x10 + i * 0x10) for i in range(count)]
            self.folders.append((fhash, pad, files))
        self.entries = []
        self.blobs = []
        for i in range(n_files):
            o = ptr_table + i * 0x18
            e = list(struct.unpack_from("<HBBiiiiI", d, o))
            self.entries.append(e)  # level,type,res,dec,comp,pad,offset,unused
            self.blobs.append(bytes(d[e[6]:e[6] + e[4]]))
        self.modified: dict[int, bytes] = {}

    def index_of(self, name: str) -> int:
        h = fnv1a64(name)
        for _, _, files in self.folders:
            for fh, idx, _ in files:
                if fh == h:
                    return idx
        return -1

    def get(self, name: str) -> bytearray | None:
        i = self.index_of(name)
        return None if i < 0 else self.get_index(i)

    def get_index(self, i: int) -> bytearray | None:
        if not (0 <= i < len(self.entries)):
            return None
        if i in self.modified:
            return bytearray(self.modified[i])
        e = self.entries[i]
        if e[1] == 0:
            return bytearray(self.blobs[i])
        if e[1] == 2:
            return bytearray(lz4_decompress(self.blobs[i], e[3]))
        raise ValueError(f"Compresión GFPak no soportada: tipo {e[1]}")

    def set_index(self, i: int, data: bytes) -> None:
        self.modified[i] = bytes(data)

    def set(self, name: str, data: bytes) -> None:
        i = self.index_of(name)
        if i < 0:
            raise KeyError(name)
        self.modified[i] = bytes(data)

    def build(self) -> bytes:
        n = len(self.entries)
        enc, table = [], []
        for i, e in enumerate(self.entries):
            if i in self.modified:
                dec = self.modified[i]
                comp = dec if e[1] == 0 else lz4_compress(dec)
                enc.append(comp)
                table.append([e[0], e[1], e[2], len(dec), len(comp), e[5], 0, e[7]])
            else:
                enc.append(self.blobs[i])
                table.append(list(e))
        nf = len(self.folders)
        ptr_hashes = 0x18 + 0x10 + nf * 8
        cur = ptr_hashes + n * 8
        folder_ptrs = []
        for _, _, files in self.folders:
            folder_ptrs.append(cur)
            cur += 0x10 + len(files) * 0x10
        ptr_table = cur
        cur = ptr_table + n * 0x18
        for i in range(n):
            table[i][6] = cur
            cur += len(enc[i])
            cur += (-cur) % 0x10
        out = bytearray()
        out += struct.pack("<QIIiiqq", GFPAK_MAGIC, self.version, self.reloc, n, nf, ptr_table, ptr_hashes)
        for p in folder_ptrs:
            out += struct.pack("<q", p)
        for h in self.hash_paths:
            out += struct.pack("<Q", h)
        for fhash, pad, files in self.folders:
            out += struct.pack("<QiI", fhash, len(files), pad)
            for fh, idx, fpad in files:
                out += struct.pack("<QiI", fh, idx, fpad)
        for t in table:
            out += struct.pack("<HBBiiiiI", *t)
        for blob in enc:
            out += blob
            out += b"\x00" * ((-len(out)) % 0x10)
        return bytes(out)


# -------------------------------------------------------------- FlatBuffers ---
class FB:
    """Acceso de solo-escalares a un FlatBuffer, editando en el sitio."""

    def __init__(self, data: bytearray):
        self.d = data

    def _u16(self, o):
        return struct.unpack_from("<H", self.d, o)[0]

    def _u32(self, o):
        return struct.unpack_from("<I", self.d, o)[0]

    def root(self) -> int:
        return self._u32(0)

    def valid_table(self, t: int) -> bool:
        if t < 4 or t + 4 > len(self.d):
            return False
        vt = t - struct.unpack_from("<i", self.d, t)[0]
        if vt < 0 or vt + 4 > len(self.d):
            return False
        vlen, olen = struct.unpack_from("<HH", self.d, vt)
        return 4 <= vlen <= 0x400 and vt + vlen <= len(self.d) and vlen % 2 == 0

    def addr(self, t: int, idx: int) -> int:
        vt = t - struct.unpack_from("<i", self.d, t)[0]
        vlen = self._u16(vt)
        slot = vt + 4 + idx * 2
        if slot + 2 > vt + vlen:
            return -1
        off = self._u16(slot)
        return -1 if off == 0 else t + off

    def tables(self, t: int, idx: int) -> list[int]:
        a = self.addr(t, idx)
        if a < 0 or a + 4 > len(self.d):
            return []
        vec = a + self._u32(a)
        if vec + 4 > len(self.d):
            return []
        n = self._u32(vec)
        if n > 20000 or vec + 4 + n * 4 > len(self.d):
            return []
        out = []
        for i in range(n):
            p = vec + 4 + i * 4
            t2 = p + self._u32(p)
            if not self.valid_table(t2):
                return []
            out.append(t2)
        return out

    def get(self, t: int, idx: int, fmt: str, default=0):
        a = self.addr(t, idx)
        if a < 0 or a + struct.calcsize(fmt) > len(self.d):
            return default
        return struct.unpack_from("<" + fmt, self.d, a)[0]

    def set(self, t: int, idx: int, fmt: str, value) -> bool:
        a = self.addr(t, idx)
        if a < 0 or a + struct.calcsize(fmt) > len(self.d):
            return False
        struct.pack_into("<" + fmt, self.d, a, value)
        return True

    def root_tables(self) -> list[int]:
        """Todas las tablas de todos los vectores de la raíz."""
        r = self.root()
        if not self.valid_table(r):
            return []
        vt = r - struct.unpack_from("<i", self.d, r)[0]
        nfields = (self._u16(vt) - 4) // 2
        out = []
        for f in range(nfields):
            out.extend(self.tables(r, f))
        return out
