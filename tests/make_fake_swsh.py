"""Genera un romfs FALSO de Espada/Escudo con la misma disposición binaria, para pruebas.

No contiene ningún dato del juego: estadísticas y tablas inventadas.
"""
import random
import struct
import sys
from pathlib import Path

import flatbuffers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nuzrandom.swsh.formats import fnv1a64, lz4_compress, GFPAK_MAGIC  # noqa: E402
from nuzrandom.swsh.items import amx_encode_cell  # noqa: E402


def table(b, fields):
    """fields: lista de (tipo, valor) en orden de índice; None = ausente."""
    b.StartObject(len(fields))
    for i, f in enumerate(fields):
        if f is None:
            continue
        kind, val = f
        {"u8": b.PrependUint8Slot, "u32": b.PrependUint32Slot, "u64": b.PrependUint64Slot,
         "i32": b.PrependInt32Slot}.get(
            kind, b.PrependUOffsetTRelativeSlot)(i, val, 0 if kind != "off" else 0)
    return b.EndObject()


def vec(b, offs):
    b.StartVector(4, len(offs), 4)
    for o in reversed(offs):
        b.PrependUOffsetTRelative(o)
    return b.EndVector()


def encounter_fb(rng, species_pool):
    b = flatbuffers.Builder(0)
    zones = []
    for z in range(5):
        subs = []
        for w in range(3):
            slots = [table(b, [("u8", 10), ("u32", rng.choice(species_pool)), ("u8", 0)]) for _ in range(4)]
            v = vec(b, slots)
            subs.append(table(b, [("u8", 5 + z), ("u8", 8 + z), ("off", v)]))
        v = vec(b, subs)
        zones.append(table(b, [("u64", 1000 + z), ("off", v)]))
    v = vec(b, zones)
    root = table(b, [("u8", 1), ("off", v)])
    b.Finish(root)
    return bytes(b.Output())


def species_list_fb(field_index, nfields, species, extra=None):
    b = flatbuffers.Builder(0)
    rows = []
    for sp in species:
        f = [None] * nfields
        f[field_index] = ("u32", sp)
        if extra is not None:
            f[extra] = ("u32", sp + 1)
        f[0] = ("u8", 3)
        rows.append(table(b, f))
    v = vec(b, rows)
    b.Finish(table(b, [("off", v)]))
    return bytes(b.Output())


def u32vec(b, vals):
    b.StartVector(4, len(vals), 4)
    for v in reversed(vals):
        b.PrependUint32(v)
    return b.EndVector()


def u64vec(b, vals):
    b.StartVector(8, len(vals), 8)
    for v in reversed(vals):
        b.PrependUint64(v)
    return b.EndVector()


def shop_fb():
    b = flatbuffers.Builder(0)
    def inv(items):
        v = u32vec(b, items)
        return table(b, [("off", v)])
    singles = []
    for items in ([4, 17, 18, 26], [213, 214, 215, 216, 217], [328, 329, 330, 331], [17, 18, 19]):
        i = inv(items)
        singles.append(table(b, [("u64", 7), ("off", i)]))
    tiers = [inv([4, 17]), inv([4, 17, 2]), inv([4, 17, 2, 3])]
    tv = vec(b, tiers)
    multi = table(b, [("u64", 9), ("off", tv)])
    v0, v1 = vec(b, singles), vec(b, [multi])
    b.Finish(table(b, [("off", v0), ("off", v1)]))
    return bytes(b.Output())


def placement_fb(z):
    b = flatbuffers.Builder(0)
    holders = []
    for k, iid in enumerate([20 + z, 1100, 30, None]):
        h = fnv1a64("") if iid is None else fnv1a64(f"item_{iid:04d}")
        hv = u64vec(b, [h])
        qv = u32vec(b, [1])
        it = table(b, [None] * 6 + [("off", hv), ("off", qv)])
        holders.append(table(b, [("off", it)]))
    chances = [table(b, [("u64", fnv1a64(f"item_{40 + k:04d}")), ("i32", 50), ("i32", 1)]) for k in range(3)]
    cv = vec(b, chances)
    ht = table(b, [None, None, ("off", cv)])
    h2 = table(b, [("off", ht)])
    hv1, hv2 = vec(b, holders), vec(b, [h2])
    fields = [None] * 20
    fields[6], fields[19] = ("off", hv1), ("off", hv2)
    zone = table(b, fields)
    zv = vec(b, [zone])
    b.Finish(table(b, [("off", zv)]))
    return bytes(b.Output())


def amx(special: dict, ncells=6000):
    cells = [special.get(i, (i % 300) << 32 | 0x2A) for i in range(ncells)]
    code = b"".join(amx_encode_cell(c) for c in cells)
    cod = 0x40
    hdr = bytearray(cod)
    struct.pack_into("<IH", hdr, 0, cod + len(code), 0xF1E0)
    struct.pack_into("<H", hdr, 10, 4)
    struct.pack_into("<III", hdr, 12, cod, cod + ncells * 8, cod + ncells * 8)
    return bytes(hdr) + code


def gfpak(files: dict) -> bytes:
    names = list(files)
    n = len(names)
    blobs = [lz4_compress(files[k]) for k in names]
    ptr_hashes = 0x18 + 0x10 + 8
    folder_ptr = ptr_hashes + n * 8
    ptr_table = folder_ptr + 0x10 + n * 0x10
    cur = ptr_table + n * 0x18
    offs = []
    for bl in blobs:
        offs.append(cur)
        cur += len(bl)
        cur += (-cur) % 0x10
    out = bytearray(struct.pack("<QIIiiqq", GFPAK_MAGIC, 0x1000, 0, n, 1, ptr_table, ptr_hashes))
    out += struct.pack("<q", folder_ptr)
    for k in names:
        out += struct.pack("<Q", fnv1a64("bin/" + k))
    out += struct.pack("<QiI", 0xABC, n, 0)
    for i, k in enumerate(names):
        out += struct.pack("<QiI", fnv1a64(k), i, 0)
    for i, k in enumerate(names):
        out += struct.pack("<HBBiiiiI", 0, 2, 0, len(files[k]), len(blobs[i]), 0, offs[i], 0)
    for bl in blobs:
        out += bl
        out += b"\0" * ((-len(out)) % 0x10)
    return bytes(out)


def main(root: Path):
    rng = random.Random(1)
    r = root / "romfs"
    def w(rel, data):
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    n = 1000
    pers = bytearray(n * 0xB0)
    for i in range(1, 899):
        o = i * 0xB0
        if i % 7 == 0:          # especies "fuera del juego"
            continue
        pers[o:o + 6] = bytes(rng.randrange(20, 130) for _ in range(6))
        pers[o + 6], pers[o + 7] = rng.randrange(18), rng.randrange(18)
        pers[o + 8] = rng.randrange(3, 255)
    w("bin/pml/personal/personal_total.bin", pers)
    learn = bytearray(b"\xff" * (n * 0x104))
    for i in range(1, 899):
        o = i * 0x104
        for k in range(6):
            struct.pack_into("<HH", learn, o + k * 4, rng.randrange(1, 600), k * 5 + 1)
    w("bin/pml/waza_oboe/wazaoboe_total.bin", learn)
    for mid in range(1, 600):
        b = flatbuffers.Builder(0)
        b.Finish(table(b, [("u32", mid), None, None, ("u8", mid % 18), None, ("u8", 1), ("u8", (mid * 7) % 120),
                           ("u8", 100), ("u8", 15), None, None, ("u32", 0), ("u32", 0), ("u32", 0), ("u32", 0),
                           ("u32", 0), ("u32", 0), ("u32", 0)]))
        data = bytes(b.Output())
        w(f"bin/pml/waza/waza{mid:04d}.wazabin", data + b"\0" * max(0, 80 - len(data)))
    for i in range(1, 899):
        evo = bytearray(8 * 9)
        if i % 3 == 1 and (i + 1) % 7:
            struct.pack_into("<HHHbB", evo, 0, 4 if i % 2 else 5, 0, i + 1, 0, 16 if i % 5 else 50)
        w(f"bin/pml/evolution/evo_{i:03d}.bin", evo)
    n_items = 1609
    mt_off = 0x44 + n_items * 2
    rec_off = mt_off + 800
    rec_off += (-rec_off) % 4
    item = bytearray(rec_off + n_items * 48)
    struct.pack_into("<H", item, 2, n_items)
    struct.pack_into("<I", item, 0x40, rec_off)
    tm_items = list(range(328, 420)) + [618, 619, 620, 690, 691, 692, 693, 1230]
    for k in range(200):
        struct.pack_into("<HH", item, mt_off + k * 4, (tm_items[k] if k < 100 else 1030 + k), 1 + k)
    for iid in range(1, n_items):
        if 1279 <= iid <= 1326 or iid % 50 == 49:
            continue                      # objetos inexistentes
        struct.pack_into("<H", item, 0x44 + iid * 2, iid)
        o = rec_off + iid * 48
        struct.pack_into("<I", item, o, 100 + iid * 10)
        item[o + 0x11] = 8 if iid in (1074, 1077, 1100) else 1
    w("bin/pml/item/item.dat", item)
    hashes = struct.pack("<I", n_items - 1) + b"".join(
        struct.pack("<QII", fnv1a64(f"item_{i:04d}"), i, 0) for i in range(1, n_items))
    w("bin/pml/item/item_hash_to_index.dat", hashes)
    w("bin/appli/shop/bin/shop_data.bin", shop_fb())
    w("bin/archive/field/resident/placement.gfpak", gfpak({f"zone{z}.bin": placement_fb(z) for z in range(3)}))
    w("bin/script/amx/main_event_0180.amx", amx({5119: (4 << 32) | 0xBC}))
    w("bin/script/amx/main_event_0300.amx", amx({5759: (1074 << 32) | 0xBC}))
    w("bin/script/amx/main_event_0340.amx", amx({6060: (367 << 32) | 0xBC}, ncells=6200))
    for t in range(1, 41):
        td = bytearray(0x18)
        td[3] = 3
        tp = bytearray()
        for s in range(3):
            rec = bytearray(0x20)
            struct.pack_into("<HHH", rec, 0x0A, 10 + t, rng.randrange(1, 898), 0)
            tp += rec
        w(f"bin/trainer/trainer_data/trainer_data_{t:03d}.bin", td)
        w(f"bin/trainer/trainer_poke/trainer_poke_{t:03d}.bin", tp)
    pool = [i for i in range(1, 899) if i % 7]
    enc = {name: encounter_fb(rng, pool) for name in ("encount_k.bin", "encount_t.bin")}
    sym_pool = pool[:60]
    enc.update({name: encounter_fb(rng, sym_pool) for name in ("encount_symbol_k.bin", "encount_symbol_t.bin")})
    w("bin/archive/field/resident/data_table.gfpak", gfpak(enc))
    w("bin/script_event_data/add_poke.bin", species_list_fb(9, 12, [810, 813, 816, 133, 150]))
    w("bin/script_event_data/field_trade.bin", species_list_fb(8, 20, [25, 52], extra=18))
    w("bin/script_event_data/event_encount_data.bin", species_list_fb(17, 20, [888, 143, 131]))
    print("romfs falso en", r)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
