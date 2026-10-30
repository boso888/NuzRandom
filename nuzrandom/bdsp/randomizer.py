"""Randomizer de Pokémon Diamante Brillante / Perla Reluciente.

DPBP guarda sus datos en AssetBundles de Unity (MonoBehaviours con typetree).
Se leen y escriben con UnityPy. Los nombres de campo se buscan de forma
tolerante (sin distinguir mayúsculas) para soportar pequeñas diferencias entre
versiones; si algo no cuadra, el botón "Diagnóstico" vuelca la estructura real.
"""
from __future__ import annotations

from pathlib import Path

from .. import settings as S
from ..core import FileStore, Log, Picker, Species, sname, species_id_from_text, TYPE_NAMES

MAX_SPECIES = 493
PERSONAL_BUNDLE = "personal_masterdatas"
MASTER_BUNDLE = "masterdatas"
STAT_KEYS = ["basic_hp", "basic_atk", "basic_def", "basic_agi", "basic_spatk", "basic_spdef"]
ENC_LISTS = ["ground_mons", "tairyo_mons", "day_mons", "night_mons", "swayGrass_mons",
             "gbaRuby_mons", "gbaSapp_mons", "gbaEme_mons", "gbaFire_mons", "gbaLeaf_mons",
             "water_mons", "boro_mons", "ii_mons", "sugoi_mons"]
BANNED_ABILITIES = {59, 121, 122, 161, 176, 197, 208, 209, 210, 211, 225, 241, 248, 258, 266, 267}
EXP_CURVES = {"rapida": 4, "media": 0, "lenta": 5}


def _unitypy():
    try:
        import UnityPy  # type: ignore
        return UnityPy
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Falta el paquete 'UnityPy'. Ejecuta Iniciar.bat para instalar dependencias.") from exc


def find_bundle(romfs: Path, name: str) -> Path | None:
    for p in Path(romfs).rglob(name):
        if p.is_file() and p.name == name:
            return p
    return None


def detect(romfs) -> bool:
    return find_bundle(Path(romfs), PERSONAL_BUNDLE) is not None


def key(d: dict, *names, default=None):
    """Busca una clave sin distinguir mayúsculas entre varios nombres posibles."""
    low = {k.lower(): k for k in d}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return default


class Bundle:
    def __init__(self, path: Path):
        self.path = path
        self.env = _unitypy().load(str(path))
        self.objs = {}
        for obj in self.env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            self.objs[str(tree.get("m_Name", ""))] = (obj, tree)
        self.dirty = set()

    def get(self, *names):
        for n in names:
            for k in self.objs:
                if k.lower() == n.lower():
                    return self.objs[k][1]
        return None

    def touch(self, tree):
        for k, (obj, t) in self.objs.items():
            if t is tree:
                self.dirty.add(k)

    def save(self) -> bytes:
        for k in self.dirty:
            obj, tree = self.objs[k]
            obj.save_typetree(tree)
        return self.env.file.save(packer="lz4")


def diagnose(romfs: Path) -> str:
    out = []
    for name in (PERSONAL_BUNDLE, MASTER_BUNDLE):
        p = find_bundle(romfs, name)
        out.append(f"### {name}: {p}")
        if not p:
            continue
        b = Bundle(p)
        for oname, (_o, tree) in sorted(b.objs.items()):
            out.append(f"- {oname}: {list(tree.keys())}")
            for k, v in tree.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    out.append(f"    {k}[{len(v)}] -> {list(v[0].keys())[:60]}")
    return "\n".join(out)


class BdspRandomizer:
    def __init__(self, store: FileStore, cfg: S.Settings, rng, log: Log):
        self.st, self.cfg, self.rng, self.log = store, cfg, rng, log
        romfs = store.romfs
        pp = find_bundle(romfs, PERSONAL_BUNDLE)
        mp = find_bundle(romfs, MASTER_BUNDLE)
        if not pp:
            raise FileNotFoundError("No se encuentra personal_masterdatas en el romfs.")
        self.pb = Bundle(pp)
        self.mb = Bundle(mp) if mp else None
        self.rel = {self.pb: str(pp.relative_to(romfs)).replace("\\", "/")}
        if self.mb:
            self.rel[self.mb] = str(mp.relative_to(romfs)).replace("\\", "/")
        self._load()

    # ------------------------------------------------------------ carga ---
    def _load(self):
        pt = self.pb.get("PersonalTable")
        if pt is None:
            raise RuntimeError("No se encontró PersonalTable. Usa 'Diagnóstico' y envía el informe.")
        self.personal_tree = pt
        self.personal = pt[key(pt, "Personal")]
        self.by_id: dict[int, dict] = {}
        self.species: dict[int, Species] = {}
        for row in self.personal:
            idx = row.get(key(row, "id"), 0)
            self.by_id[idx] = row
            mon = row.get(key(row, "monsno"), idx)
            if 0 < idx <= MAX_SPECIES and mon == idx:
                stats = [int(row.get(key(row, k), 0)) for k in STAT_KEYS]
                valid = row.get(key(row, "valid_flag"), 1)
                self.species[idx] = Species(idx, stats, (row.get(key(row, "type1"), 0), row.get(key(row, "type2"), 0)),
                                            in_game=bool(valid) and sum(stats) > 0)
        et = self.pb.get("EvolveTable")
        self.evo_tree = et
        self.evolve = et[key(et, "Evolve")] if et else []
        for row in self.evolve:
            src = row.get(key(row, "id"), 0)
            ar = row.get(key(row, "ar"), [])
            for k in range(0, len(ar) - 4, 5):
                method, tgt = ar[k], ar[k + 2]
                if method and src in self.species and tgt in self.species and tgt != src:
                    if tgt not in self.species[src].evolves_to:
                        self.species[src].evolves_to.append(tgt)
                    if not self.species[tgt].evolves_from:
                        self.species[tgt].evolves_from = src
        wt = self.pb.get("WazaTable")
        self.waza_tree = wt
        self.moves: dict[int, dict] = {}
        if wt:
            for row in wt[key(wt, "Waza")]:
                mid = row.get(key(row, "wazaNo"), 0)
                if mid and row.get(key(row, "isValid"), 1):
                    self.moves[mid] = row
        lt = self.pb.get("WazaOboeTable")
        self.learn_tree = lt
        self.learn = lt[key(lt, "WazaOboe")] if lt else []
        it = self.pb.get("ItemTable")
        self.item_tree = it
        self.machines = it[key(it, "WazaMachine")] if it and key(it, "WazaMachine") else []
        used = set()
        for row in self.learn:
            ar = row.get(key(row, "ar"), [])
            used.update(ar[1::2])
        used.update(m.get(key(m, "wazaNo"), 0) for m in self.machines)
        banned = {0, 165} | ({12, 32, 90, 329} if self.cfg.ban_ohko else set())
        self.move_pool = sorted(m for m in used if m not in banned and (not self.moves or m in self.moves))
        self.picker = Picker(self.species, self.rng, MAX_SPECIES, self.cfg.generation_filter)

    def mprop(self, mid, *names, default=0):
        row = self.moves.get(mid)
        if not row:
            return default
        k = key(row, *names)
        return row.get(k, default) if k else default

    # --------------------------------------------------------- ejecutar ---
    def run(self):
        steps = [
            ("Datos de los Pokémon", self.do_personal),
            ("Evoluciones", self.do_evolutions),
            ("Datos de movimientos", self.do_move_data),
            ("MT", self.do_tms),
            ("Movimientos por nivel", self.do_learnsets),
            ("Pokémon salvajes", self.do_wild),
            ("Entrenadores y jefes", self.do_trainers),
            ("Precios", self.do_prices),
            ("Tiendas", self.do_shops),
        ]
        for name, fn in steps:
            self.log.info(f"· {name}…")
            fn()
        for b in (self.pb, self.mb):
            if b and b.dirty:
                self.st.write(self.rel[b], b.save())
        c = self.cfg
        if c.starter_mode != S.UNCHANGED or c.static_mode != S.UNCHANGED or c.gift_mode != S.UNCHANGED \
                or c.field_items_random or c.gift_items_random:
            self.log.add("Avisos", "DPBP: starters, Pokémon regalados, encuentros fijos y objetos del suelo o "
                                   "regalados viven en los scripts del juego y todavía no se aleatorizan.")

    # ------------------------------------------------- datos de pokémon ---
    def do_personal(self):
        c = self.cfg
        if c.types_mode == S.UNCHANGED and c.abilities_mode == S.UNCHANGED and c.stats_mode == S.UNCHANGED \
                and c.min_catch_rate <= 0 and c.exp_curve == S.UNCHANGED and c.tm_compat_mode == S.UNCHANGED:
            return
        groups = self.picker.families() if c.follow_evolutions else [[s] for s in self.species]
        abil_pool = [a for a in range(1, 268) if a not in BANNED_ABILITIES and (c.abilities_wonder_guard or a != 25)]
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
                row, sp = self.by_id[sid], self.species[sid]
                if types:
                    row[key(row, "type1")], row[key(row, "type2")] = types
                    sp.types = types
                if abil:
                    for k, a in zip(("tokusei1", "tokusei2", "tokusei3"), abil):
                        if key(row, k):
                            row[key(row, k)] = a
                if c.stats_mode in ("mezclar", "redistribuir") and sid != 292:
                    if c.stats_mode == "mezclar":
                        new = [sp.stats[order[k]] for k in range(6)]
                    else:
                        tot = sum(weights)
                        new = [max(1, min(255, round(sp.bst * w / tot))) for w in weights]
                        new[0] = max(new[0], 20)
                    for k, v in zip(STAT_KEYS, new):
                        row[key(row, k)] = v
                    sp.stats = new
                kr = key(row, "get_rate")
                if c.min_catch_rate > 0 and kr and row[kr] < c.min_catch_rate:
                    row[kr] = min(255, c.min_catch_rate)
                ke = key(row, "give_exp", "exp_value")
                if c.exp_yield_percent != 100 and ke:
                    row[ke] = max(1, min(0xFFFF, round(row[ke] * c.exp_yield_percent / 100)))
                kg = key(row, "grow")
                if c.exp_curve in EXP_CURVES and kg:
                    row[kg] = EXP_CURVES[c.exp_curve]
        if c.tm_compat_mode != S.UNCHANGED:
            tm_types = [self.mprop(m.get(key(m, "wazaNo"), 0), "type", default=-1) for m in self.machines]
            for sid, sp in self.species.items():
                row = self.by_id[sid]
                words = [0, 0, 0, 0]
                for k in range(min(128, len(tm_types) or 100)):
                    on = c.tm_compat_mode == "todos" or self.rng.random() < (
                        0.75 if (k < len(tm_types) and tm_types[k] in sp.types) else 0.30)
                    if on:
                        words[k // 32] |= 1 << (k % 32)
                for w in range(4):
                    kk = key(row, f"machine{w + 1}")
                    if kk:
                        row[kk] = words[w]
        self.pb.touch(self.personal_tree)
        if c.types_mode == S.RANDOM:
            for sid, sp in sorted(self.species.items()):
                if sp.in_game:
                    t = TYPE_NAMES[sp.types[0]] + ("" if sp.types[0] == sp.types[1] else "/" + TYPE_NAMES[sp.types[1]])
                    self.log.add("Tipos", f"{sname(sid)}: {t}")

    def _new_level(self, lvl):
        c = self.cfg
        if lvl <= 0:
            return lvl
        if c.evo_level_mode == "tope":
            return min(lvl, max(2, c.evo_level_cap))
        if c.evo_level_mode == "porcentaje":
            return max(2, round(lvl * c.evo_level_percent / 100))
        return lvl

    def do_evolutions(self):
        from ..swsh.randomizer import FRIENDSHIP, TRADE_EVO, SPECIAL, LEVEL_METHODS
        c = self.cfg
        if not self.evolve:
            return
        easy = max(1, min(100, c.evo_easy_level))
        pool = self.picker.pool(True)
        for row in self.evolve:
            src = row.get(key(row, "id"), 0)
            ar = row.get(key(row, "ar"), [])
            for k in range(0, len(ar) - 4, 5):
                m = ar[k]
                if not m:
                    continue
                if (c.evo_easy and m in FRIENDSHIP | TRADE_EVO) or (c.evo_special_to_level and m in SPECIAL):
                    ar[k], ar[k + 1], ar[k + 4] = 4, 0, self._new_level(easy)
                    self.log.add("Evoluciones", f"{sname(src)} → {sname(ar[k + 2])}: ahora a nivel {ar[k + 4]}")
                elif m in LEVEL_METHODS and c.evo_level_mode != S.UNCHANGED:
                    # en DPBP el nivel puede estar en el parámetro o en el campo de nivel
                    for idx in (k + 4, k + 1):
                        if 0 < ar[idx] <= 100:
                            new = self._new_level(ar[idx])
                            if new != ar[idx]:
                                self.log.add("Evoluciones", f"{sname(src)} → {sname(ar[k + 2])}: nivel {ar[idx]} → {new}")
                                ar[idx] = new
                            break
                if c.evo_mode != S.UNCHANGED and 0 < ar[k + 2] <= MAX_SPECIES:
                    new = self.picker.pick(ar[k + 2], c.evo_mode, pool, avoid={src})
                    if new != ar[k + 2]:
                        self.log.add("Evoluciones", f"{sname(src)} ahora evoluciona en {sname(new)} (antes {sname(ar[k + 2])})")
                        ar[k + 2], ar[k + 3] = new, 0
        self.pb.touch(self.evo_tree)

    def do_move_data(self):
        c = self.cfg
        if not c.move_data_random or not self.moves:
            return
        for mid in self.move_pool:
            row = self.moves.get(mid)
            if not row:
                continue
            kp, ka, kpp, kt = key(row, "power"), key(row, "hitPer"), key(row, "basePP"), key(row, "type")
            if c.move_power and kp and row[kp] > 1:
                row[kp] = self.rng.randrange(20, 155, 5)
            if c.move_accuracy and ka and 0 < row[ka] <= 100:
                row[ka] = self.rng.randrange(70, 105, 5)
            if c.move_pp and kpp and row[kpp] > 0:
                row[kpp] = self.rng.randrange(5, 45, 5)
            if c.move_type and kt:
                row[kt] = self.rng.randrange(18)
        self.pb.touch(self.waza_tree)
        self.log.add("Movimientos", "Potencia/precisión/PP/tipo aleatorizados según ajustes.")

    def do_tms(self):
        if self.cfg.tm_moves_mode == S.UNCHANGED or not self.machines:
            return
        pool = list(self.move_pool)
        self.rng.shuffle(pool)
        for i, m in enumerate(self.machines):
            k = key(m, "wazaNo")
            if k and i < len(pool):
                m[k] = pool[i]
                self.log.add("MT", f"MT{i + 1:02d}: movimiento #{pool[i]}")
        self.pb.touch(self.item_tree)

    def do_learnsets(self):
        c = self.cfg
        if c.learnset_mode == S.UNCHANGED or not self.learn:
            return
        weak = [m for m in self.move_pool if 30 <= self.mprop(m, "power") <= 60]
        for row in self.learn:
            sid = row.get(key(row, "id"), 0)
            ar = row.get(key(row, "ar"), [])
            prow = self.by_id.get(sid, {})
            types = (prow.get(key(prow, "type1") or "", -1), prow.get(key(prow, "type2") or "", -1))
            stab = [m for m in self.move_pool if self.mprop(m, "type", default=-1) in types]
            used = set()
            for k in range(1, len(ar), 2):
                src = stab if stab and self.rng.random() < 0.4 else self.move_pool
                if k == 1 and c.learnset_damaging_first and weak:
                    src = [m for m in weak if self.mprop(m, "type") in types] or weak
                mv = self.rng.choice(src)
                for _ in range(20):
                    if mv not in used:
                        break
                    mv = self.rng.choice(self.move_pool)
                used.add(mv)
                ar[k] = mv
        self.pb.touch(self.learn_tree)
        self.log.add("Movimientos por nivel", "Movimientos aleatorios conservando los niveles originales.")

    def moves_at(self, sid, level):
        got = []
        for row in self.learn:
            if row.get(key(row, "id")) == sid:
                ar = row.get(key(row, "ar"), [])
                for k in range(0, len(ar) - 1, 2):
                    if ar[k] <= level:
                        if ar[k + 1] in got:
                            got.remove(ar[k + 1])
                        got.append(ar[k + 1])
                break
        got = got[-4:]
        return got + [0] * (4 - len(got))

    # ---------------------------------------------------------- salvajes ---
    def do_wild(self):
        c = self.cfg
        if not self.mb or (c.wild_mode == S.UNCHANGED and not c.wild_level_percent):
            return
        lo, hi = c.wild_min_bst, c.wild_max_bst
        pool = self.picker.pool(c.wild_legendaries, extra=lambda sp: (lo <= 0 or sp.bst >= lo) and (hi <= 0 or sp.bst <= hi))
        maps, summary = {}, {}
        for tname in ("EncountTableD", "EncountTableP", "EncountTable_d", "EncountTable_p"):
            tree = self.mb.get(tname)
            if tree is None:
                continue
            for zone in tree.get(key(tree, "table") or "", []):
                zid = zone.get(key(zone, "zoneID"), 0)
                for ln in ENC_LISTS:
                    kl = key(zone, ln)
                    if not kl:
                        continue
                    for slot in zone[kl] or []:
                        km, klo, khi = key(slot, "monsNo"), key(slot, "minlv"), key(slot, "maxlv")
                        if c.wild_level_percent and klo and khi:
                            f = 1 + c.wild_level_percent / 100
                            for kk in (klo, khi):
                                if 0 < slot[kk] <= 100:
                                    slot[kk] = max(1, min(100, round(slot[kk] * f)))
                        if c.wild_mode == S.UNCHANGED or not km:
                            continue
                        sp = slot[km] & 0xFFFF
                        if not (0 < sp <= MAX_SPECIES):
                            continue
                        mkey = {"hueco": None, "zona": (zid, sp), "global": sp,
                                "uno_por_zona": zid}.get(c.wild_mapping, (zid, sp))
                        if mkey is not None and mkey in maps:
                            new = maps[mkey]
                        else:
                            new = self.picker.pick(sp, c.wild_mode, pool)
                            if mkey is not None:
                                maps[mkey] = new
                        slot[km] = new
                        summary.setdefault(sp, set()).add(new)
            self.mb.touch(tree)
        for sp in sorted(summary):
            self.log.add("Salvajes", f"{sname(sp)} → " + ", ".join(sname(x) for x in sorted(summary[sp])))

    # ------------------------------------------------------- entrenadores ---
    BOSS_WORDS = ("leader", "champ", "rival", "boss", "bigfour", "big4", "shitenno", "tenno", "galactic", "galaxy",
                  "ginga", "commander", "kanbu", "cyrus", "akagi", "jimu", "gym", "elite")

    def boss_ids(self, tt) -> set[int]:
        types = tt.get(key(tt, "TrainerType") or "", [])
        boss_types = set()
        for i, row in enumerate(types):
            text = " ".join(str(v).lower() for v in row.values() if isinstance(v, str))
            if any(w in text for w in self.BOSS_WORDS):
                boss_types.add(row.get(key(row, "TrainerID", "ID") or "", i))
        out = set()
        for i, row in enumerate(tt.get(key(tt, "TrainerData") or "", [])):
            if row.get(key(row, "TypeID") or "", -1) in boss_types:
                out.add(i)
        from ..core import parse_ids
        out |= set(parse_ids(self.cfg.boss_extra_ids))
        out -= set(parse_ids(self.cfg.boss_excluded_ids))
        return out

    def do_trainers(self):
        c = self.cfg
        if not self.mb:
            return
        tt = self.mb.get("TrainerTable")
        if tt is None:
            self.log.info("  (no se encontró TrainerTable)")
            return
        data_rows = tt.get(key(tt, "TrainerData") or "", [])
        bosses = self.boss_ids(tt)
        n_boss = 0
        for i, row in enumerate(tt.get(key(tt, "TrainerPoke") or "", [])):
            tid = row.get(key(row, "ID") or "", i)
            boss = tid in bosses or i in bosses
            mode = c.boss_mode if boss and c.boss_mode != S.SAME_AS_TRAINERS else c.trainer_mode
            legend = c.boss_legendaries if boss else c.trainer_legendaries
            lo = c.boss_min_bst if boss else 0
            pool = self.picker.pool(legend, extra=(lambda sp: sp.bst >= lo) if lo > 0 else None)
            theme = None
            if mode == S.TYPE_THEME:
                theme = self.rng.randrange(18)
                pool = [p for p in pool if theme in self.species[p].types] or pool
                mode = S.SIMILAR
            team = [n for n in range(1, 7) if key(row, f"P{n}MonsNo") and row[key(row, f"P{n}MonsNo")]]
            if not team:
                continue
            orig = len(team)
            if boss and c.boss_full_teams and len(team) < 6:
                last = team[-1]
                for n in range(len(team) + 1, 7):
                    for k in list(row):
                        if k.lower().startswith(f"p{last}"):
                            nk = key(row, f"P{n}" + k[2:])
                            if nk:
                                row[nk] = row[k]
                    team.append(n)
                n_boss += 1
            lvl_pct = c.trainer_level_percent + (c.boss_level_percent if boss else 0)
            evolve_at = c.boss_force_evolved_level if boss else c.trainer_force_evolved_level
            used, after = set(), []
            for pos, n in enumerate(team):
                km, kl, kf = key(row, f"P{n}MonsNo"), key(row, f"P{n}Level"), key(row, f"P{n}FormNo")
                sp, lv = row[km], row.get(kl, 1) if kl else 1
                if lvl_pct and kl:
                    lv = max(1, min(100, round(lv * (1 + lvl_pct / 100))))
                    row[kl] = lv
                new_slot = pos >= orig
                slot_mode = mode if mode != S.UNCHANGED or not new_slot else S.SIMILAR
                new = sp if not (0 < sp <= MAX_SPECIES) else self.picker.pick(
                    sp, slot_mode, pool, avoid=used if c.trainer_no_duplicates else None)
                new = self.picker.evolve_for_level(new, lv, evolve_at)
                used.add(new)
                if new != sp or new_slot:
                    row[km] = new
                    if kf:
                        row[kf] = 0
                    if c.trainer_levelup_moves:
                        for w, mv in enumerate(self.moves_at(new, lv), start=1):
                            kw = key(row, f"P{n}Waza{w}")
                            if kw:
                                row[kw] = mv
                if c.trainer_random_natures and key(row, f"P{n}Seikaku"):
                    row[key(row, f"P{n}Seikaku")] = self.rng.randrange(25)
                if c.trainer_perfect_ivs or (boss and c.boss_perfect_ivs):
                    for st in ("Hp", "Atk", "Def", "SpAtk", "SpDef", "Agi"):
                        kt = key(row, f"P{n}Talent{st}")
                        if kt:
                            row[kt] = 31
                after.append(f"{sname(new)} Nv.{lv}")
            if (c.trainer_max_ai or (boss and c.boss_max_ai)) and i < len(data_rows):
                ka = key(data_rows[i], "AIBit")
                if ka:
                    data_rows[i][ka] = 0xFFFF if data_rows[i][ka] <= 0xFFFF else 0xFFFFFFFF
            label = f"{'JEFE ' if boss else ''}Entrenador {tid}" + (f" [{TYPE_NAMES[theme]}]" if theme is not None else "")
            self.log.add("Jefes" if boss else "Entrenadores", f"{label}: " + ", ".join(after))
        self.mb.touch(tt)
        self.log.add("Jefes", f"{len(bosses)} jefes detectados; {n_boss} ampliados a 6 Pokémon.")

    # ------------------------------------------------------ precios/tiendas ---
    def do_prices(self):
        from ..swsh.items import VALUABLES, RARE_CANDY
        c = self.cfg
        it = self.item_tree
        rows = it.get(key(it, "Item") or "", []) if it else []
        n = 0
        for row in rows:
            iid, kp = row.get(key(row, "no", "ItemNo", "id") or "", 0), key(row, "price")
            if not kp or row[kp] <= 0:
                continue
            if iid == RARE_CANDY and c.mart_rare_candy:
                row[kp] = max(1, c.rare_candy_price)
                continue
            if c.shop_price_percent != 100 and not (c.shop_keep_valuables and iid in VALUABLES):
                row[kp] = max(1, round(row[kp] * c.shop_price_percent / 100))
                n += 1
        if rows:
            self.pb.touch(it)
            self.log.add("Tiendas", f"Precios al {c.shop_price_percent} % en {n} objetos.")

    def do_shops(self):
        from ..swsh.items import MAX_REPEL, RARE_CANDY, EVO_ITEMS, TM_ITEMS, _GENERAL_RANGES, parse_item_list, pick_item
        c = self.cfg
        st = self.mb.get("ShopTable") if self.mb else None
        if st is None:
            self.log.info("  (no se encontró ShopTable)")
            return
        exclude = set(parse_item_list(c.items_exclude, {}))
        general = [i for a, b in _GENERAL_RANGES for i in range(a, b + 1) if i < 700 and i not in exclude]
        evo = [i for i in EVO_ITEMS if i < 700 and i not in exclude]
        fs = st.get(key(st, "FS") or "", [])
        if fs:
            extras = ([MAX_REPEL] if c.mart_max_repel else []) + ([RARE_CANDY] if c.mart_rare_candy else []) \
                + parse_item_list(c.mart_extra_items, {})
            have = {r.get(key(r, "ItemNo") or "", 0) for r in fs}
            for iid in extras:
                if iid in have:
                    for r in fs:
                        if r.get(key(r, "ItemNo")) == iid and key(r, "BadgeNum"):
                            r[key(r, "BadgeNum")] = 0
                    continue
                new = dict(fs[0])
                new[key(new, "ItemNo")] = iid
                if key(new, "BadgeNum"):
                    new[key(new, "BadgeNum")] = 0
                fs.insert(0, new)
            if extras:
                self.log.add("Tiendas", f"Tienda principal desde el inicio: objetos {extras}")
        fixed = st.get(key(st, "FixedShop") or "", [])
        by_shop: dict = {}
        for r in fixed:
            by_shop.setdefault(r.get(key(r, "ShopID") or "", 0), []).append(r)
        for sid, rows in by_shop.items():
            ki = [key(r, "ItemNo") for r in rows]
            vals = [r[k] for r, k in zip(rows, ki) if k]
            is_tm = sum(1 for v in vals if 328 <= v <= 427) * 2 > len(vals)
            if (is_tm and not c.shops_tm_random) or (not is_tm and not c.shops_secondary_random):
                continue
            used = set()
            for r, k in zip(rows, ki):
                if not k:
                    continue
                for _ in range(30):
                    nv = self.rng.choice(range(328, 428)) if is_tm else pick_item(self.rng, general, evo, c.shops_evo_percent)
                    if nv not in used:
                        break
                used.add(nv)
                r[k] = nv
        self.mb.touch(st)
        self.log.add("Tiendas", f"{len(by_shop)} tiendas fijas revisadas (secundarias y de MT aleatorias según ajustes).")
