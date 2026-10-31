"""Randomizer de Pokémon Espada / Escudo (romfs 1.3.x)."""
from __future__ import annotations

import re
import struct
from pathlib import Path

from .. import settings as S
from ..core import FileStore, Log, Picker, Species, TYPE_NAMES, sname, species_id_from_text
from . import items as IT
from .formats import FB, Gfpak
from .text import load_names

MAX_SPECIES = 898

PERSONAL = "bin/pml/personal/personal_total.bin"
LEARNSET = "bin/pml/waza_oboe/wazaoboe_total.bin"
EVO_DIR = "bin/pml/evolution"
ITEM = IT.ITEM
WAZA_DIR = "bin/pml/waza"
TR_DATA = "bin/trainer/trainer_data"
TR_POKE = "bin/trainer/trainer_poke"
DATA_TABLE = "bin/archive/field/resident/data_table.gfpak"
ADD_POKE = "bin/script_event_data/add_poke.bin"
TRADE = "bin/script_event_data/field_trade.bin"
EVENT_ENC = "bin/script_event_data/event_encount_data.bin"

P_SIZE = 0xB0
L_SIZE = 0x104
T_SIZE = 0x20
EVO_SIZE, EVO_PER = 8, 9

HIDDEN_FILES = ("encount_k.bin", "encount_t.bin")
SYMBOL_FILES = ("encount_symbol_k.bin", "encount_symbol_t.bin")
STARTERS = (810, 813, 816)
GRASS, FIRE, WATER = 11, 9, 10

# Combates importantes de la historia (gimnasios, rivales, villanos, campeón).
# Fuente: orden de combates de PokeFeur Randomizer SWSH.
FIRST_RIVAL = {4, 5, 6}
BOSS_TRAINERS = {
    7, 8, 9, 197, 198, 199, 191, 192, 193, 121, 122, 123, 156, 157, 158, 124, 125, 126, 127, 128, 129,
    202, 203, 204, 130, 131, 132, 153, 154, 155,               # Paul (Hop)
    195, 240, 133,                                             # Bede
    196, 138, 145,                                             # Roxy (Marnie)
    32, 36, 37, 77, 78, 108, 135, 136, 107, 144, 134, 137,     # líderes de gimnasio
    143, 175, 149,                                             # Olivia, Rose, Lionel
}

# Métodos de evolución (pkNX EvolutionType, gen 8)
FRIENDSHIP = {1, 2, 3}
TRADE_EVO = {5, 6, 7}
SPECIAL = {16, 19, 20, 21, 22, 25, 26, 27, 28, 29, 30, 31, 39, 40, 41, 43, 44, 45, 48, 49}
LEVEL_METHODS = {4, 9, 10, 11, 12, 13, 14, 15, 23, 24, 32, 33, 34, 36, 37, 38, 46, 47}

BANNED_ABILITIES = {59, 121, 122, 161, 176, 197, 208, 209, 210, 211, 225, 241, 248, 258, 266, 267}
WONDER_GUARD = 25
ABILITY_MAX = 267
EXP_CURVES = {"rapida": 4, "media": 0, "lenta": 5}
EXCLUDED_MOVES = {0, 165} | set(range(622, 659)) | set(range(695, 704)) | {719, 743} | set(range(723, 729)) | set(range(757, 775))
OHKO = {12, 32, 90, 329}
HELD_BATTLE_ITEMS = list(range(213, 301)) + [537, 538, 539, 540, 541, 542, 543, 544, 545, 546, 547, 639, 640,
                                             1118, 1119, 1120, 1121, 1122, 1123]

REQUIRED = [PERSONAL, LEARNSET, ITEM]


def detect(romfs) -> bool:
    return (Path(romfs) / PERSONAL).is_file()


def validate(store: FileStore) -> list[str]:
    problems = [f"Falta {r}" for r in REQUIRED if not store.exists(r)]
    if store.exists(PERSONAL) and len(store.read(PERSONAL)) % P_SIZE:
        problems.append("personal_total.bin no tiene el tamaño esperado (¿versión distinta de 1.3.x?)")
    return problems


class SwShRandomizer:
    def __init__(self, store: FileStore, cfg: S.Settings, rng, log: Log):
        self.st, self.cfg, self.rng, self.log = store, cfg, rng, log
        self.personal = store.read(PERSONAL)
        self.n_personal = len(self.personal) // P_SIZE
        self.learn = store.read(LEARNSET)
        self.species: dict[int, Species] = {}
        self.evos: dict[str, bytearray] = {}
        self.moves: dict[int, dict] = {}
        self.wazafiles: dict[int, str] = {}
        self.items = IT.Items(store)
        self.item = self.items.data
        self.move_names = load_names(store.romfs, "wazaname.dat")
        self._load()

    # ------------------------------------------------------------ carga ---
    def _p(self, i: int) -> int:
        return i * P_SIZE

    def mname(self, mid: int) -> str:
        return self.move_names[mid] if 0 < mid < len(self.move_names) and self.move_names[mid] else f"movimiento #{mid}"

    def _load(self):
        for i in range(1, min(MAX_SPECIES, self.n_personal - 1) + 1):
            o = self._p(i)
            stats = list(self.personal[o:o + 6])
            self.species[i] = Species(i, stats, (self.personal[o + 6], self.personal[o + 7]), in_game=sum(stats) > 0)
        for rel in self.st.glob(EVO_DIR, "evo_*.bin"):
            m = re.search(r"evo_(\d+)\.bin$", rel)
            if not m:
                continue
            src = int(m.group(1))
            data = self.st.read(rel)
            self.evos[rel] = data
            if src not in self.species:
                continue
            for k in range(min(EVO_PER, len(data) // EVO_SIZE)):
                method, _arg, tgt = struct.unpack_from("<HHH", data, k * EVO_SIZE)
                if method and 0 < tgt <= MAX_SPECIES and tgt != src and tgt in self.species:
                    if tgt not in self.species[src].evolves_to:
                        self.species[src].evolves_to.append(tgt)
                    if not self.species[tgt].evolves_from:
                        self.species[tgt].evolves_from = src
        for rel in self.st.glob(WAZA_DIR, "*.wazabin"):
            m = re.search(r"(\d+)\.wazabin$", rel)
            if not m:
                continue
            mid = int(m.group(1))
            data = self.st.read(rel)
            if len(data) <= 64:
                continue
            fb = FB(data)
            t = fb.root()
            if not fb.valid_table(t):
                continue
            self.wazafiles[mid] = rel
            self.moves[mid] = {"type": fb.get(t, 3, "B"), "cat": fb.get(t, 5, "B"),
                               "power": fb.get(t, 6, "B"), "acc": fb.get(t, 7, "B"), "pp": fb.get(t, 8, "B")}
        ptr = struct.unpack_from("<H", self.item, 2)[0]
        self.tm_off = 0x44 + ptr * 2
        if self.tm_off + 800 > len(self.item):
            self.tm_off = -1
        used = set()
        for sid in range(self.n_personal):
            used.update(m for m, _ in self.learnset(sid))
        used.update(self.tm_moves())
        banned = EXCLUDED_MOVES | (OHKO if self.cfg.ban_ohko else set())
        self.move_pool = sorted(m for m in used if m not in banned and (not self.moves or m in self.moves))
        self.picker = Picker(self.species, self.rng, MAX_SPECIES, self.cfg.generation_filter)

    def learnset(self, idx: int) -> list[tuple[int, int]]:
        o = idx * L_SIZE
        out = []
        if o + L_SIZE > len(self.learn):
            return out
        for c in range(0, L_SIZE, 4):
            mv, lv = struct.unpack_from("<HH", self.learn, o + c)
            if mv == 0xFFFF and lv == 0xFFFF:
                break
            if mv:
                out.append((mv, lv))
        return out

    def tm_moves(self) -> list[int]:
        if self.tm_off < 0:
            return []
        return [struct.unpack_from("<HH", self.item, self.tm_off + i * 4)[1] for i in range(200)]

    def bst_filter(self, lo: int, hi: int):
        if lo <= 0 and hi <= 0:
            return None
        return lambda s: (lo <= 0 or s.bst >= lo) and (hi <= 0 or s.bst <= hi)

    # --------------------------------------------------------- ejecutar ---
    def run(self):
        steps = [
            ("Datos de los Pokémon", self.do_personal),
            ("Evoluciones", self.do_evolutions),
            ("Datos de movimientos", self.do_move_data),
            ("MT / DT", self.do_tms),
            ("Movimientos por nivel", self.do_learnsets),
            ("Pokémon salvajes", self.do_wild),
            ("Encuentros fijos", self.do_static),
            ("Starters y regalos", self.do_gifts),
            ("Intercambios", self.do_trades),
            ("Entrenadores y jefes", self.do_trainers),
            ("Precios", lambda: IT.do_prices(self.items, self.cfg, self.log)),
            ("Tiendas", lambda: IT.do_shops(self.st, self.items, self.cfg, self.rng, self.log)),
            ("Objetos del suelo", lambda: IT.do_field_items(self.st, self.items, self.cfg, self.rng, self.log)),
            ("Objetos regalados", lambda: IT.do_gift_items(self.st, self.items, self.cfg, self.rng, self.log)),
        ]
        for name, fn in steps:
            self.log.info(f"· {name}…")
            try:
                fn()
            except FileNotFoundError as e:
                self.log.info(f"  (omitido: no se encontró {e.filename})")
        self.st.write(PERSONAL, self.personal)
        self.st.write(LEARNSET, self.learn)
        self.items.save()

    # ------------------------------------------------- datos de pokémon ---
    def do_personal(self):
        c = self.cfg
        groups = self.picker.families() if c.follow_evolutions else [[s] for s in self.species]
        abil_pool = [a for a in range(1, ABILITY_MAX + 1) if a not in BANNED_ABILITIES
                     and (c.abilities_wonder_guard or a != WONDER_GUARD)]
        held_pool = self.items.general_pool(set()) if c.wild_held_items_random else []
        for fam in groups:
            fam = [s for s in fam if self.species[s].in_game]
            if not fam:
                continue
            types = None
            if c.types_mode == S.RANDOM:
                t1 = self.rng.randrange(18)
                t2 = t1 if self.rng.random() < 0.45 else self.rng.choice([t for t in range(18) if t != t1])
                types = (t1, t2)
            abil = [self.rng.choice(abil_pool) for _ in range(3)] if c.abilities_mode == S.RANDOM else None
            weights = [self.rng.random() + 0.25 for _ in range(6)]
            order = list(range(6))
            self.rng.shuffle(order)
            for sid in fam:
                o = self._p(sid)
                sp = self.species[sid]
                if types:
                    self.personal[o + 6], self.personal[o + 7] = types
                    sp.types = types
                if abil:
                    struct.pack_into("<HHH", self.personal, o + 0x18, *abil)
                if c.stats_mode == "mezclar" and sid != 292:
                    new = [sp.stats[order[k]] for k in range(6)]
                    self.personal[o:o + 6] = bytes(new)
                    sp.stats = new
                elif c.stats_mode == "redistribuir" and sid != 292:
                    tot = sum(weights)
                    new = [max(1, min(255, round(sp.bst * w / tot))) for w in weights]
                    new[0] = max(new[0], 20)
                    self.personal[o:o + 6] = bytes(new)
                    sp.stats = new
                if c.min_catch_rate > 0 and self.personal[o + 8] < c.min_catch_rate:
                    self.personal[o + 8] = min(255, c.min_catch_rate)
                if c.exp_curve in EXP_CURVES:
                    self.personal[o + 0x15] = EXP_CURVES[c.exp_curve]
                if c.exp_yield_percent != 100:
                    base = struct.unpack_from("<H", self.personal, o + 0x22)[0]
                    struct.pack_into("<H", self.personal, o + 0x22, max(1, min(0xFFFF, round(base * c.exp_yield_percent / 100))))
                if held_pool:
                    for off, chance in ((0x0C, 0.5), (0x0E, 0.2), (0x10, 0.05)):
                        val = self.rng.choice(held_pool) if self.rng.random() < chance else 0
                        struct.pack_into("<H", self.personal, o + off, val)
        if c.tm_compat_mode != S.UNCHANGED:
            self._tm_compat()
        if c.types_mode == S.RANDOM:
            for sid, sp in sorted(self.species.items()):
                if sp.in_game:
                    t = TYPE_NAMES[sp.types[0]] + ("" if sp.types[0] == sp.types[1] else "/" + TYPE_NAMES[sp.types[1]])
                    self.log.add("Tipos", f"{sname(sid)}: {t}")
        if c.min_catch_rate > 0:
            self.log.add("Pokémon", f"Ratio de captura mínimo: {c.min_catch_rate}.")
        if c.exp_yield_percent != 100:
            self.log.add("Pokémon", f"Experiencia obtenida al {c.exp_yield_percent} %.")

    def _tm_compat(self):
        tms = self.tm_moves()
        for sid, sp in self.species.items():
            if not sp.in_game:
                continue
            o = self._p(sid)
            for base, moves in ((0x28, tms[:100]), (0x3C, tms[100:])):
                bits = bytearray(16)
                for k in range(100):
                    if self.cfg.tm_compat_mode == "todos":
                        on = True
                    else:
                        mt = self.moves.get(moves[k] if k < len(moves) else 0, {}).get("type", -1)
                        on = self.rng.random() < (0.75 if mt in sp.types else 0.30)
                    if on:
                        bits[k >> 3] |= 1 << (k & 7)
                self.personal[o + base:o + base + 16] = bits

    # ------------------------------------------------------- evoluciones ---
    def _new_level(self, lvl: int) -> int:
        c = self.cfg
        if lvl <= 0:
            return lvl
        if c.evo_level_mode == "tope":
            return min(lvl, max(2, c.evo_level_cap))
        if c.evo_level_mode == "porcentaje":
            return max(2, round(lvl * c.evo_level_percent / 100))
        return lvl

    def do_evolutions(self):
        c = self.cfg
        easy_lvl = max(1, min(100, c.evo_easy_level))
        counts = {"amistad/intercambio": 0, "especiales": 0, "adelantadas": 0}
        pool = self.picker.pool(True)
        for rel, data in self.evos.items():
            src = int(re.search(r"evo_(\d+)", rel).group(1))
            touched = False
            for k in range(min(EVO_PER, len(data) // EVO_SIZE)):
                o = k * EVO_SIZE
                method, arg, tgt = struct.unpack_from("<HHH", data, o)
                if not method or not tgt:
                    continue
                if (c.evo_easy and method in FRIENDSHIP | TRADE_EVO) or (c.evo_special_to_level and method in SPECIAL):
                    struct.pack_into("<HH", data, o, 4, 0)    # 4 = subir de nivel
                    data[o + 7] = self._new_level(easy_lvl)
                    counts["amistad/intercambio" if method in FRIENDSHIP | TRADE_EVO else "especiales"] += 1
                    if src <= MAX_SPECIES:
                        self.log.add("Evoluciones", f"{sname(src)} → {sname(tgt)}: ahora a nivel {data[o + 7]}")
                    method = 4
                    touched = True
                elif method in LEVEL_METHODS and c.evo_level_mode != S.UNCHANGED:
                    new = self._new_level(data[o + 7])
                    if new != data[o + 7]:
                        if src <= MAX_SPECIES:
                            self.log.add("Evoluciones", f"{sname(src)} → {sname(tgt)}: nivel {data[o + 7]} → {new}")
                        data[o + 7] = new
                        counts["adelantadas"] += 1
                        touched = True
                if c.evo_mode != S.UNCHANGED and src <= MAX_SPECIES and tgt <= MAX_SPECIES:
                    new = self.picker.pick(tgt, c.evo_mode, pool, avoid={src})
                    if new != tgt:
                        struct.pack_into("<H", data, o + 4, new)
                        data[o + 6] = 0
                        self.log.add("Evoluciones", f"{sname(src)} ahora evoluciona en {sname(new)} (antes {sname(tgt)})")
                        touched = True
            if touched:
                self.st.write(rel, data)
        self.log.add("Evoluciones", "Resumen: " + ", ".join(f"{v} {k}" for k, v in counts.items()))

    # --------------------------------------------------------- movimientos ---
    def do_move_data(self):
        c = self.cfg
        if not c.move_data_random:
            return
        for mid in self.move_pool:
            rel = self.wazafiles.get(mid)
            if not rel:
                continue
            data = self.st.read(rel)
            fb = FB(data)
            t = fb.root()
            m = self.moves[mid]
            if c.move_power and m["power"] > 1:
                m["power"] = self.rng.randrange(20, 155, 5)
                fb.set(t, 6, "B", m["power"])
            if c.move_accuracy and 0 < m["acc"] <= 100:
                m["acc"] = self.rng.randrange(70, 105, 5)
                fb.set(t, 7, "B", m["acc"])
            if c.move_pp and m["pp"] > 0:
                m["pp"] = self.rng.randrange(5, 45, 5)
                fb.set(t, 8, "B", m["pp"])
            if c.move_type and fb.addr(t, 3) >= 0:
                m["type"] = self.rng.randrange(18)
                fb.set(t, 3, "B", m["type"])
            self.st.write(rel, data)
            self.log.add("Movimientos", f"{self.mname(mid)}: potencia {m['power']}, precisión {m['acc']}, PP {m['pp']}, "
                                        f"tipo {TYPE_NAMES[m['type']] if m['type'] < 18 else m['type']}")

    def do_tms(self):
        if self.cfg.tm_moves_mode == S.UNCHANGED or self.tm_off < 0:
            return
        pool = list(self.move_pool)
        self.rng.shuffle(pool)
        for i, mv in enumerate(pool[:200]):
            struct.pack_into("<H", self.item, self.tm_off + i * 4 + 2, mv)
            self.log.add("MT / DT", f"{'MT' if i < 100 else 'DT'}{i % 100:02d}: {self.mname(mv)}")
        self.items.dirty = True

    def do_learnsets(self):
        c = self.cfg
        if c.learnset_mode == S.UNCHANGED:
            return
        weak = [m for m in self.move_pool if 30 <= self.moves.get(m, {}).get("power", 0) <= 60]
        for idx in range(1, self.n_personal):
            ls = self.learnset(idx)
            if not ls:
                continue
            types = (self.personal[self._p(idx) + 6], self.personal[self._p(idx) + 7])
            stab = [m for m in self.move_pool if self.moves.get(m, {}).get("type") in types]
            used, new = set(), []
            for k, (_mv, lv) in enumerate(ls):
                src = stab if stab and self.rng.random() * 100 < c.learnset_stab_percent else self.move_pool
                if k == 0 and c.learnset_damaging_first and weak:
                    src = [m for m in weak if self.moves[m]["type"] in types] or weak
                mv = self.rng.choice(src)
                for _ in range(20):
                    if mv not in used:
                        break
                    mv = self.rng.choice(self.move_pool)
                used.add(mv)
                new.append((mv, lv))
            o = idx * L_SIZE
            for k, (mv, lv) in enumerate(new):
                struct.pack_into("<HH", self.learn, o + k * 4, mv, lv)
        self.log.add("Movimientos por nivel", "Movimientos aleatorios conservando los niveles originales.")

    def moves_at(self, sid: int, level: int) -> list[int]:
        got = []
        for mv, lv in self.learnset(sid):
            if lv <= level:
                if mv in got:
                    got.remove(mv)
                got.append(mv)
        got = got[-4:]
        return got + [0] * (4 - len(got))

    # ---------------------------------------------------------- salvajes ---
    def do_wild(self):
        c = self.cfg
        if not self.st.exists(DATA_TABLE):
            self.log.info("  (no está data_table.gfpak)")
            return
        if c.wild_mode == S.UNCHANGED and not c.wild_level_percent:
            return
        pack = Gfpak(self.st.read(DATA_TABLE))
        files = {n: d for n in HIDDEN_FILES + SYMBOL_FILES if (d := pack.get(n)) is not None}
        symbol_vanilla = set()
        for name in SYMBOL_FILES:
            if name in files:
                fb = FB(files[name])
                for _z, _w, slot in self._iter_slots(fb):
                    sp = fb.get(slot, 1, "I")
                    if 0 < sp <= MAX_SPECIES:
                        symbol_vanilla.add(sp)
        flt = self.bst_filter(c.wild_min_bst, c.wild_max_bst)
        pool_hidden = self.picker.pool(c.wild_legendaries, extra=flt)
        pool_symbol = self.picker.pool(c.wild_legendaries, restrict=sorted(symbol_vanilla), extra=flt) \
            if symbol_vanilla else pool_hidden
        maps: dict = {}
        summary: dict[int, set] = {}
        for name, data in files.items():
            is_symbol = name in SYMBOL_FILES
            randomize = c.wild_mode != S.UNCHANGED and (c.wild_overworld or not is_symbol)
            pool = pool_symbol if is_symbol else pool_hidden
            fb = FB(data)
            touched = False
            if c.wild_level_percent:
                f = 1 + c.wild_level_percent / 100
                for zt in fb.tables(fb.root(), 1):
                    for sub in fb.tables(zt, 1):
                        for fi in (0, 1):
                            lv = fb.get(sub, fi, "B")
                            if 0 < lv <= 100:
                                fb.set(sub, fi, "B", max(1, min(100, round(lv * f))))
                                touched = True
            if randomize:
                kind = "sym" if is_symbol else "hid"
                for zone, _w, slot in self._iter_slots(fb):
                    sp = fb.get(slot, 1, "I")
                    if not (0 < sp <= MAX_SPECIES):
                        continue
                    key = {"hueco": None, "zona": (kind, zone, sp), "global": (kind, sp),
                           "uno_por_zona": (kind, zone)}.get(c.wild_mapping, (kind, zone, sp))
                    if key is not None and key in maps:
                        new = maps[key]
                    else:
                        new = self.picker.pick(sp, c.wild_mode, pool)
                        if key is not None:
                            maps[key] = new
                    fb.set(slot, 1, "I", new)
                    fb.set(slot, 2, "B", 0)
                    summary.setdefault(sp, set()).add(new)
                    touched = True
            if touched:
                pack.set(name, data)
        self.st.write(DATA_TABLE, pack.build())
        for sp in sorted(summary):
            self.log.add("Salvajes", f"{sname(sp)} → " + ", ".join(sname(x) for x in sorted(summary[sp])))
        if c.wild_level_percent:
            self.log.add("Salvajes", f"Niveles salvajes {c.wild_level_percent:+d} %.")

    def battle_pool(self) -> list[int]:
        """Especies posibles en el combate oculto: mismos filtros que los salvajes."""
        c = self.cfg
        return self.picker.pool(c.wild_legendaries, extra=self.bst_filter(c.wild_min_bst, c.wild_max_bst))

    def _iter_slots(self, fb: FB):
        r = fb.root()
        if not fb.valid_table(r):
            return
        for zt in fb.tables(r, 1):
            zone = fb.get(zt, 0, "Q")
            for w, sub in enumerate(fb.tables(zt, 1)):
                if w >= 9:
                    continue
                for slot in fb.tables(sub, 2):
                    yield zone, w, slot

    # --------------------------------------------- estáticos / regalos ---
    def _species_field(self, rel, field_ids, mode, legend, keep_legend, section):
        if mode == S.UNCHANGED or not self.st.exists(rel):
            return
        data = self.st.read(rel)
        fb = FB(data)
        pool = self.picker.pool(legend)
        n = 0
        for t in fb.root_tables():
            for fi in field_ids:
                sp = fb.get(t, fi, "I")
                if not (0 < sp <= MAX_SPECIES):
                    continue
                if keep_legend and sp in self.species and self.species[sp].legendary:
                    continue
                new = self.picker.pick(sp, mode, pool)
                if new != sp and fb.set(t, fi, "I", new):
                    self.log.add(section, f"{sname(sp)} → {sname(new)}")
                    n += 1
        if n:
            self.st.write(rel, data)

    def do_static(self):
        c = self.cfg
        self._species_field(EVENT_ENC, (17,), c.static_mode, c.static_legendaries,
                            c.static_keep_story_legendaries, "Encuentros fijos")

    def do_trades(self):
        c = self.cfg
        self._species_field(TRADE, (8, 18), c.trade_mode, c.gift_legendaries, True, "Intercambios")

    def choose_starters(self) -> list[int]:
        c = self.cfg
        if c.starter_mode == S.CUSTOM:
            ids = [species_id_from_text(x) for x in c.starter_custom]
            if all(i and i > 0 and i in self.species for i in ids):
                return ids
            self.log.info("  Starters personalizados no válidos: se eligen al azar.")
            self.log.add("Avisos", f"Starters personalizados no reconocidos: {c.starter_custom}")

        def ok(s: Species) -> bool:
            if c.starter_basic_only and not (s.basic and s.evolves_to):
                return False
            if c.starter_three_stages and not any(self.species[e].evolves_to for e in s.evolves_to if e in self.species):
                return False
            return True

        pool = self.picker.pool(c.starter_legendaries, extra=ok)
        chosen: list[int] = []
        for slot, orig in enumerate(STARTERS):
            cands = [p for p in pool if p not in chosen]
            if c.starter_type_triangle:
                want = (GRASS, FIRE, WATER)[slot]
                cands = [p for p in cands if want in self.species[p].types] or cands
            if c.starter_distinct_types:
                taken = {t for s in chosen for t in self.species[s].types}
                cands = [p for p in cands if not (set(self.species[p].types) & taken)] or cands
            chosen.append(self.picker.pick(orig, S.SIMILAR if c.starter_mode == S.SIMILAR else S.RANDOM, cands))
        return chosen

    def do_gifts(self):
        c = self.cfg
        if not self.st.exists(ADD_POKE):
            return
        data = self.st.read(ADD_POKE)
        fb = FB(data)
        new_starters = self.choose_starters() if c.starter_mode != S.UNCHANGED else list(STARTERS)
        smap = dict(zip(STARTERS, new_starters))
        pool = self.picker.pool(c.gift_legendaries)
        n = 0
        for t in fb.root_tables():
            sp = fb.get(t, 9, "I")
            if not (0 < sp <= MAX_SPECIES):
                continue
            if sp in smap:
                new = smap[sp]
                if new != sp and fb.set(t, 9, "I", new):
                    self.log.add("Starters", f"{sname(sp)} → {sname(new)}")
                    n += 1
            elif c.gift_mode != S.UNCHANGED and not (sp in self.species and self.species[sp].legendary):
                new = self.picker.pick(sp, c.gift_mode, pool)
                if new != sp and fb.set(t, 9, "I", new):
                    self.log.add("Regalos", f"{sname(sp)} → {sname(new)}")
                    n += 1
        if n:
            self.st.write(ADD_POKE, data)
            if c.starter_mode != S.UNCHANGED:
                self.log.add("Starters", "Nota: el equipo de Paul no se ajusta a tus nuevos starters.")

    # ------------------------------------------------------- entrenadores ---
    def do_trainers(self):
        c = self.cfg
        files = self.st.glob(TR_POKE, "trainer_poke_*.bin")
        if not files:
            return
        from ..core import parse_ids
        bosses = set(BOSS_TRAINERS) | (FIRST_RIVAL if c.boss_include_first_rival else set())
        bosses = (bosses | set(parse_ids(c.boss_extra_ids))) - set(parse_ids(c.boss_excluded_ids))
        held = self.items.usable(HELD_BATTLE_ITEMS)
        n_boss = 0
        for rel in files:
            num = re.search(r"trainer_poke_(\d+)\.bin$", rel).group(1)
            tid = int(num)
            drel = f"{TR_DATA}/trainer_data_{num}.bin"
            if not self.st.exists(drel):
                continue
            tdata = self.st.read(drel)
            party = self.st.read(rel)
            orig_bytes = (bytes(tdata), bytes(party))
            nrec = len(party) // T_SIZE
            team = tdata[3] if len(tdata) > 3 and 0 < tdata[3] <= nrec else nrec
            if team == 0:
                continue
            boss = tid in bosses
            mode = c.boss_mode if boss and c.boss_mode != S.SAME_AS_TRAINERS else c.trainer_mode
            legend = c.boss_legendaries if boss else c.trainer_legendaries
            flt = self.bst_filter(c.boss_min_bst, 0) if boss else None
            pool = self.picker.pool(legend, extra=flt)
            theme = None
            if mode == S.TYPE_THEME:
                theme = self.rng.randrange(18)
                pool = [p for p in pool if theme in self.species[p].types] or pool
                mode = S.SIMILAR
            lvl_pct = c.trainer_level_percent + (c.boss_level_percent if boss else 0)
            evolve_at = c.boss_force_evolved_level if boss else c.trainer_force_evolved_level
            orig_team = team
            if boss and c.boss_full_teams and team < 6:
                last = bytes(party[(team - 1) * T_SIZE: team * T_SIZE])
                party = party[:team * T_SIZE]
                while team < 6:
                    party += last
                    team += 1
                tdata[3] = team
                n_boss += 1
            levels = [struct.unpack_from("<H", party, s * T_SIZE + 0x0A)[0] for s in range(orig_team)]
            top = max(levels) if levels else 5
            used: set[int] = set()
            after = []
            for s in range(team):
                o = s * T_SIZE
                sp = struct.unpack_from("<H", party, o + 0x0C)[0]
                if not sp:
                    continue
                is_new_slot = s >= orig_team
                lv = top if is_new_slot else struct.unpack_from("<H", party, o + 0x0A)[0]
                if lvl_pct:
                    lv = max(1, min(100, round(lv * (1 + lvl_pct / 100))))
                struct.pack_into("<H", party, o + 0x0A, lv)
                slot_mode = mode if mode != S.UNCHANGED or not is_new_slot else S.SIMILAR
                avoid = used if c.trainer_no_duplicates else None
                new = sp if sp > MAX_SPECIES else self.picker.pick(sp, slot_mode, pool, avoid=avoid)
                new = self.picker.evolve_for_level(new, lv, evolve_at)
                used.add(new)
                if new != sp or is_new_slot:
                    struct.pack_into("<HH", party, o + 0x0C, new, 0)
                    if c.trainer_levelup_moves:
                        struct.pack_into("<HHHH", party, o + 0x12, *self.moves_at(new, lv))
                if c.trainer_random_natures:
                    party[o + 1] = self.rng.randrange(25)
                if c.trainer_perfect_ivs or (boss and c.boss_perfect_ivs):
                    iv = struct.unpack_from("<I", party, o + 0x1C)[0]
                    struct.pack_into("<I", party, o + 0x1C, (iv & 0xC0000000) | 0x3FFFFFFF)
                if boss and c.boss_held_items and held:
                    struct.pack_into("<H", party, o + 0x10, self.rng.choice(held))
                after.append(f"{sname(new)} Nv.{lv}")
            if (c.trainer_max_ai or (boss and c.boss_max_ai)) and len(tdata) >= 0x10:
                struct.pack_into("<I", tdata, 0x0C, 0xFFFFFFFF)
            if (bytes(tdata), bytes(party)) == orig_bytes:
                continue
            self.st.write(rel, party)
            self.st.write(drel, tdata)
            label = f"{'JEFE ' if boss else ''}Entrenador {num}" + (f" [{TYPE_NAMES[theme]}]" if theme is not None else "")
            self.log.add("Jefes" if boss else "Entrenadores", f"{label}: " + ", ".join(after))
        if c.boss_full_teams:
            self.log.add("Jefes", f"{n_boss} combates importantes ampliados a 6 Pokémon; el resto mantiene su tamaño original.")
