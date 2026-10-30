"""Objetos de Espada/Escudo: precios, tiendas, objetos del suelo y regalos de NPC.

Disposiciones verificadas por PokeFeur Randomizer SWSH (GPLv3) y KM-Editor
(GPLv3). Todo se edita en el sitio salvo las listas de la tienda principal, que
se alargan añadiendo un vector nuevo al final del FlatBuffer y redirigiendo el
puntero (los desplazamientos de FlatBuffers siempre apuntan hacia delante).
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from .. import settings as S
from ..core import DATA_DIR, FileStore, Log
from .formats import FB, Gfpak
from .text import load_names

ITEM = "bin/pml/item/item.dat"
ITEM_HASH = "bin/pml/item/item_hash_to_index.dat"
SHOP = "bin/appli/shop/bin/shop_data.bin"
PLACEMENT = "bin/archive/field/resident/placement.gfpak"
AMX_DIR = "bin/script/amx"

ITEM_COUNT = 1609
REC_SIZE = 48
POCKET_OFF = 0x11
POCKET_KEY = 8
EMPTY_HASH = 0xCBF29CE484222645

POKE_BALL, POTION, MAX_REPEL, RARE_CANDY = 4, 17, 43, 50

EVO_ITEMS = [80, 81, 82, 83, 84, 85, 107, 108, 109, 110, 221, 226, 227, 233, 235, 252, 321, 322, 323, 324, 325,
             326, 327, 537, 646, 647, 849, 1109, 1110, 1111, 1112, 1113, 1114, 1115, 1116, 1117, 1253, 1254,
             1582, 1592]
VALUABLES = {86, 87, 88, 89, 90, 91, 92, 106, 580, 581, 582, 583} | set(range(584, 592))
TM_ITEMS = list(range(328, 420)) + [618, 619, 620, 690, 691, 692, 693, 1230]
TR_ITEMS = list(range(1130, 1230))
_GENERAL_RANGES = [(1, 63), (76, 92), (106, 110), (149, 326), (485, 500), (537, 547), (565, 582), (639, 650),
                   (795, 796), (849, 851), (879, 884), (1084, 1099), (1105, 1129), (1231, 1264)]
OPCODE_PUSH_C = 0xBC


def parse_item_list(text: str, names: dict[str, int]) -> list[int]:
    """'43, Caramelo Raro, 50' -> [43, 50, 50]; ignora lo que no reconoce."""
    out = []
    for part in (text or "").replace(";", ",").split(","):
        p = part.strip()
        if not p:
            continue
        if p.isdigit():
            out.append(int(p))
        elif _norm(p) in names:
            out.append(names[_norm(p)])
    return out


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if c.isalnum())


class Items:
    def __init__(self, store: FileStore):
        self.st = store
        self.data = store.read(ITEM)
        self.rec_off = struct.unpack_from("<I", self.data, 0x40)[0]
        self.count = min(ITEM_COUNT, max(0, (self.rec_off - 0x44) // 2))
        self.n_rec = (len(self.data) - self.rec_off) // REC_SIZE if self.rec_off < len(self.data) else 0
        self.names = load_names(store.romfs, "itemname.dat")
        self.by_name = {_norm(n): i for i, n in enumerate(self.names) if n}
        self.dirty = False

    # ---------------------------------------------------------- consultas ---
    def rec(self, iid: int) -> int:
        if not (0 < iid < self.count):
            return -1
        r = struct.unpack_from("<H", self.data, 0x44 + iid * 2)[0]
        return r if 0 < r < self.n_rec else -1

    def exists(self, iid: int) -> bool:
        return self.rec(iid) > 0

    def pocket(self, iid: int) -> int:
        r = self.rec(iid)
        return self.data[self.rec_off + r * REC_SIZE + POCKET_OFF] if r > 0 else -1

    def is_key(self, iid: int) -> bool:
        return self.pocket(iid) == POCKET_KEY

    def price(self, iid: int) -> int:
        r = self.rec(iid)
        return struct.unpack_from("<I", self.data, self.rec_off + r * REC_SIZE)[0] if r > 0 else 0

    def set_price(self, iid: int, value: int) -> None:
        r = self.rec(iid)
        if r > 0:
            struct.pack_into("<I", self.data, self.rec_off + r * REC_SIZE, max(0, min(999999, value)))
            self.dirty = True

    def name(self, iid: int) -> str:
        if 0 < iid < len(self.names) and self.names[iid]:
            return f"{self.names[iid]}"
        return f"Objeto #{iid}"

    def usable(self, ids) -> list[int]:
        return [i for i in ids if self.exists(i) and not self.is_key(i)]

    def general_pool(self, exclude: set[int]) -> list[int]:
        ids = [i for a, b in _GENERAL_RANGES for i in range(a, b + 1)]
        return [i for i in self.usable(ids) if i not in exclude]

    def evo_pool(self, exclude: set[int]) -> list[int]:
        return [i for i in self.usable(EVO_ITEMS) if i not in exclude]

    def save(self):
        if self.dirty:
            self.st.write(ITEM, self.data)


def pick_item(rng, general: list[int], evo: list[int], evo_pct: int, extra: list[int] | None = None) -> int:
    if evo and rng.random() * 100 < evo_pct:
        return rng.choice(evo)
    pool = general + (extra or [])
    return rng.choice(pool) if pool else POTION


# ----------------------------------------------------------------- precios ---
def do_prices(items: Items, cfg: S.Settings, log: Log):
    pct = cfg.shop_price_percent
    if pct != 100:
        seen, n = set(), 0
        for iid in range(1, items.count):
            r = items.rec(iid)
            if r <= 0 or r in seen:
                continue
            seen.add(r)
            if cfg.shop_keep_valuables and iid in VALUABLES:
                continue
            p = items.price(iid)
            if p <= 0:
                continue
            items.set_price(iid, max(1, round(p * pct / 100)))
            n += 1
        log.add("Tiendas", f"Precios al {pct} % en {n} objetos"
                + (" (los objetos para vender, como las Pepitas, conservan su valor)." if cfg.shop_keep_valuables else "."))
    if cfg.mart_rare_candy and items.exists(RARE_CANDY):
        items.set_price(RARE_CANDY, max(1, cfg.rare_candy_price))
        log.add("Tiendas", f"{items.name(RARE_CANDY)} a {max(1, cfg.rare_candy_price)} ₽.")


# ----------------------------------------------------------------- tiendas ---
def _int_vector(fb: FB, table: int):
    a = fb.addr(table, 0)
    if a < 0 or a + 4 > len(fb.d):
        return None
    vec = a + struct.unpack_from("<I", fb.d, a)[0]
    if vec + 4 > len(fb.d):
        return None
    n = struct.unpack_from("<I", fb.d, vec)[0]
    if n == 0 or n > 500 or vec + 4 + n * 4 > len(fb.d):
        return None
    vals = [struct.unpack_from("<I", fb.d, vec + 4 + k * 4)[0] for k in range(n)]
    if not all(0 < v < 2000 for v in vals):
        return None
    return a, vec, vals


def shop_inventories(fb: FB):
    """Lista de (campo_vector, posición_vector, objetos)."""
    out = []
    r = fb.root()
    if not fb.valid_table(r):
        return out
    vt = r - struct.unpack_from("<i", fb.d, r)[0]
    nfields = (struct.unpack_from("<H", fb.d, vt)[0] - 4) // 2
    for f in range(nfields):
        for shop in fb.tables(r, f):
            a = fb.addr(shop, 1)
            if a < 0:
                continue
            target = a + struct.unpack_from("<I", fb.d, a)[0]
            direct = _int_vector(fb, target) if fb.valid_table(target) else None
            if direct:
                out.append(direct)
                continue
            for inv in fb.tables(shop, 1):
                got = _int_vector(fb, inv)
                if got:
                    out.append(got)
    return out


def append_vector(data: bytearray, field_addr: int, values: list[int]) -> None:
    while len(data) % 4:
        data.append(0)
    pos = len(data)
    data += struct.pack("<I", len(values)) + b"".join(struct.pack("<I", v) for v in values)
    struct.pack_into("<I", data, field_addr, pos - field_addr)


def do_shops(store: FileStore, items: Items, cfg: S.Settings, rng, log: Log):
    if not store.exists(SHOP):
        log.info("  (no se encontró shop_data.bin)")
        return
    data = store.read(SHOP)
    fb = FB(data)
    invs = shop_inventories(fb)
    if not invs:
        log.info("  (estructura de tiendas no reconocida)")
        return
    exclude = set(parse_item_list(cfg.items_exclude, items.by_name))
    extras = []
    if cfg.mart_max_repel:
        extras.append(MAX_REPEL)
    if cfg.mart_rare_candy:
        extras.append(RARE_CANDY)
    extras += parse_item_list(cfg.mart_extra_items, items.by_name)
    extras = [e for i, e in enumerate(extras) if items.exists(e) and not items.is_key(e) and e not in extras[:i]]
    general = items.general_pool(exclude)
    evo = items.evo_pool(exclude)
    tms = items.usable(TM_ITEMS)
    trs = items.usable(TR_ITEMS)
    tmset, trset = set(TM_ITEMS), set(TR_ITEMS)
    stats = {"main": 0, "tm": 0, "sec": 0}
    appended = []
    for field_addr, vec, vals in invs:
        n_tm = sum(1 for v in vals if v in tmset or v in trset)
        if POKE_BALL in vals and POTION in vals:
            stats["main"] += 1
            new = [e for e in extras if e not in vals] + vals
            if len(new) != len(vals):
                appended.append((field_addr, new))
            continue
        if n_tm * 2 > len(vals):
            if not cfg.shops_tm_random:
                continue
            stats["tm"] += 1
            used = set()
            for k, v in enumerate(vals):
                src = trs if v in trset else tms
                cands = [x for x in src if x not in used and x not in exclude] or src
                if cands:
                    nv = rng.choice(cands)
                    used.add(nv)
                    struct.pack_into("<I", data, vec + 4 + k * 4, nv)
            continue
        if not cfg.shops_secondary_random:
            continue
        stats["sec"] += 1
        used, line = set(), []
        for k in range(len(vals)):
            for _ in range(30):
                nv = pick_item(rng, general, evo, cfg.shops_evo_percent)
                if nv not in used:
                    break
            used.add(nv)
            line.append(items.name(nv))
            struct.pack_into("<I", data, vec + 4 + k * 4, nv)
        log.add("Tiendas", "Tienda secundaria: " + ", ".join(line))
    for field_addr, new in appended:   # al final, para no mover nada leído antes
        append_vector(data, field_addr, new)
    store.write(SHOP, data)
    if extras:
        log.add("Tiendas", "Tienda principal (desde el principio): " + ", ".join(items.name(e) for e in extras))
    log.add("Tiendas", f"Inventarios: {stats['main']} de tienda principal (solo precio y añadidos), "
                       f"{stats['tm']} de MT/DT aleatorios, {stats['sec']} secundarios aleatorios.")


# ---------------------------------------------------------- objetos suelo ---
def _hash_lookup(store: FileStore):
    if not store.exists(ITEM_HASH):
        return {}, {}
    d = store.read(ITEM_HASH)
    n = struct.unpack_from("<I", d, 0)[0]
    if 4 + n * 16 != len(d):
        return {}, {}
    by_id, by_hash = {}, {}
    for i in range(n):
        h, iid = struct.unpack_from("<QI", d, 4 + i * 16)
        by_id.setdefault(iid, h)
        by_hash[h] = iid
    return by_id, by_hash


def _u64_vector(fb: FB, table: int, idx: int) -> list[int]:
    a = fb.addr(table, idx)
    if a < 0 or a + 4 > len(fb.d):
        return []
    vec = a + struct.unpack_from("<I", fb.d, a)[0]
    if vec + 4 > len(fb.d):
        return []
    n = struct.unpack_from("<I", fb.d, vec)[0]
    if n > 10000:
        return []
    return [vec + 4 + k * 8 for k in range(n) if vec + 12 + k * 8 <= len(fb.d)]


def _nested(fb: FB, table: int, idx: int) -> int:
    a = fb.addr(table, idx)
    if a < 0 or a + 4 > len(fb.d):
        return -1
    t = a + struct.unpack_from("<I", fb.d, a)[0]
    return t if fb.valid_table(t) else -1


def do_field_items(store: FileStore, items: Items, cfg: S.Settings, rng, log: Log):
    if not (cfg.field_items_random or cfg.hidden_items_random) or not store.exists(PLACEMENT):
        return
    by_id, by_hash = _hash_lookup(store)
    if not by_id:
        log.info("  (no se pudo leer item_hash_to_index.dat)")
        return
    exclude = set(parse_item_list(cfg.items_exclude, items.by_name))
    general = [i for i in items.general_pool(exclude) if i in by_id]
    evo = [i for i in items.evo_pool(exclude) if i in by_id]
    extra = [i for i in items.usable(TM_ITEMS + TR_ITEMS) if i in by_id and i not in exclude] if cfg.items_include_tms else []
    pack = Gfpak(store.read(PLACEMENT))
    ground = hidden = protected = 0
    for idx in range(len(pack.entries)):
        try:
            d = pack.get_index(idx)
        except ValueError:
            continue
        if d is None or len(d) < 16:
            continue
        fb = FB(d)
        r = fb.root()
        if not fb.valid_table(r):
            continue
        touched = False
        try:
            for zone in fb.tables(r, 0):
                addrs = []
                if cfg.field_items_random:
                    for holder in fb.tables(zone, 6):
                        it = _nested(fb, holder, 0)
                        if it >= 0:
                            addrs += [("g", a) for a in _u64_vector(fb, it, 6)]
                if cfg.hidden_items_random:
                    for holder in fb.tables(zone, 19):
                        ht = _nested(fb, holder, 0)
                        if ht >= 0:
                            for ch in fb.tables(ht, 2):
                                a = fb.addr(ch, 0)
                                if a >= 0:
                                    addrs.append(("h", a))
                for kind, a in addrs:
                    h = struct.unpack_from("<Q", d, a)[0]
                    if h == EMPTY_HASH or h not in by_hash:
                        continue
                    if items.is_key(by_hash[h]):
                        protected += 1
                        continue
                    new = pick_item(rng, general, evo, cfg.items_evo_percent, extra)
                    struct.pack_into("<Q", d, a, by_id[new])
                    touched = True
                    if kind == "g":
                        ground += 1
                    else:
                        hidden += 1
        except (struct.error, IndexError):
            continue
        if touched:
            pack.set_index(idx, d)
    if ground or hidden:
        store.write(PLACEMENT, pack.build())
    log.add("Objetos", f"Objetos del suelo aleatorios: {ground} visibles, {hidden} ocultos "
                       f"({protected} objetos clave protegidos).")


# ------------------------------------------------------------ regalos NPC ---
def _amx_decode(d: bytes):
    if len(d) < 0x20:
        return None
    size, magic = struct.unpack_from("<IH", d, 0)
    flags = struct.unpack_from("<H", d, 10)[0]
    cod, _dat, hea = struct.unpack_from("<3I", d, 12)
    if magic not in (0xF1E0, 0xF1E1, 0xF1E2) or not (flags & 4) or size > len(d) or cod >= size:
        return None
    comp = d[cod:size]
    cells, bounds = [], []
    i = len(comp)
    while i > 0:
        end, c, shift = i, 0, 0
        while True:
            i -= 1
            c |= (comp[i] & 0x7F) << shift
            shift += 7
            if i == 0 or (comp[i - 1] & 0x80) == 0:
                break
        if comp[i] & 0x40:
            while shift < 64:
                c |= 0xFF << shift
                shift += 8
        cells.append(c & 0xFFFFFFFFFFFFFFFF)
        bounds.append((i, end))
    cells.reverse()
    bounds.reverse()
    if len(cells) != (hea - cod) // 8:
        return None
    return cells, bounds, cod


def amx_encode_cell(value: int) -> bytes:
    groups = []
    while True:
        groups.append(value & 0x7F)
        value >>= 7
        if value == 0:
            break
    groups.reverse()
    if groups[0] & 0x40:
        groups.insert(0, 0)
    return bytes((g | 0x80) if k < len(groups) - 1 else g for k, g in enumerate(groups))


def do_gift_items(store: FileStore, items: Items, cfg: S.Settings, rng, log: Log):
    if not cfg.gift_items_random:
        return
    facts = json.loads((DATA_DIR / "swsh_npc_gifts.json").read_text(encoding="utf-8"))["gifts"]
    exclude = set(parse_item_list(cfg.items_exclude, items.by_name))
    general = items.general_pool(exclude)
    evo = items.evo_pool(exclude)
    extra = [i for i in items.usable(TM_ITEMS + TR_ITEMS) if i not in exclude] if cfg.items_include_tms else []
    by_file: dict[str, list] = {}
    for amx, cell, item, label in facts:
        by_file.setdefault(amx, []).append((cell, item, label))
    changed = protected = 0
    for amx, entries in by_file.items():
        rel = f"{AMX_DIR}/{amx}"
        if not store.exists(rel):
            continue
        d = store.read(rel)
        if struct.unpack_from("<I", d, 0)[0] != len(d):
            continue  # cabecera inesperada: el módulo no es el que creemos
        dec = _amx_decode(bytes(d))
        if not dec:
            continue
        cells, bounds, cod = dec
        edits = []
        for cell, item, label in entries:
            if cell >= len(cells) or (cells[cell] & 0xFFFFFFFF) != OPCODE_PUSH_C or (cells[cell] >> 32) != item:
                continue  # no coincide con este juego/versión: no se toca
            if items.is_key(item):
                protected += 1
                continue
            new = pick_item(rng, general, evo, cfg.items_evo_percent, extra)
            edits.append((bounds[cell], new, item))
        if not edits:
            continue
        for (start, end), new, old in sorted(edits, key=lambda e: -e[0][0]):
            d[cod + start:cod + end] = amx_encode_cell((new << 32) | OPCODE_PUSH_C)
            log.add("Objetos", f"Regalo: {items.name(old)} → {items.name(new)}")
            changed += 1
        struct.pack_into("<I", d, 0, len(d))
        store.write(rel, d)
    log.add("Objetos", f"{changed} objetos regalados aleatorizados ({protected} objetos clave protegidos).")
