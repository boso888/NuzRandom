"""Lógica común a los dos juegos: especies, reservas de candidatos, elección y registro."""
from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from . import settings as S

DATA_DIR = Path(__file__).parent / "data"

LEGENDARIES = {
    144, 145, 146, 150, 151, 243, 244, 245, 249, 250, 251, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386,
    480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 490, 491, 492, 493, 494, 638, 639, 640, 641, 642, 643, 644,
    645, 646, 647, 648, 649, 716, 717, 718, 719, 720, 721, 772, 773, 785, 786, 787, 788, 789, 790, 791, 792, 793,
    794, 795, 796, 797, 798, 799, 800, 801, 802, 803, 804, 805, 806, 807, 808, 809, 888, 889, 890, 891, 892, 893,
    894, 895, 896, 897, 898,
}

TYPE_NAMES = ["Normal", "Lucha", "Volador", "Veneno", "Tierra", "Roca", "Bicho", "Fantasma", "Acero",
              "Fuego", "Agua", "Planta", "Eléctrico", "Psíquico", "Hielo", "Dragón", "Siniestro", "Hada"]

GEN_RANGES = [(1, 151), (152, 251), (252, 386), (387, 493), (494, 649), (650, 721), (722, 809), (810, 898)]

_NAMES: list[str] | None = None


def species_names() -> list[str]:
    global _NAMES
    if _NAMES is None:
        with open(DATA_DIR / "species_es.json", encoding="utf-8") as fh:
            _NAMES = json.load(fh)
    return _NAMES


def sname(sid: int) -> str:
    names = species_names()
    return f"{names[sid - 1]} (#{sid})" if 0 < sid <= len(names) else f"#{sid}"


def species_id_from_text(text: str) -> int:
    """Acepta un número o un nombre (sin importar mayúsculas/acentos)."""
    text = (text or "").strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    norm = _norm(text)
    for i, n in enumerate(species_names(), start=1):
        if _norm(n) == norm:
            return i
    return -1


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if c.isalnum())


def parse_ids(text: str) -> list[int]:
    """'12, 40-42' -> [12, 40, 41, 42]"""
    out = []
    for part in (text or "").replace(";", ",").split(","):
        part = part.strip()
        if "-" in part:
            a, _, b = part.partition("-")
            if a.strip().isdigit() and b.strip().isdigit():
                out.extend(range(int(a), int(b) + 1))
        elif part.isdigit():
            out.append(int(part))
    return out


def generation_of(sid: int) -> int:
    for g, (a, b) in enumerate(GEN_RANGES, start=1):
        if a <= sid <= b:
            return g
    return 9


@dataclass
class Species:
    id: int
    stats: list[int]          # PS, Atq, Def, Vel, AtEsp, DefEsp
    types: tuple[int, int]
    in_game: bool = True
    evolves_to: list[int] = field(default_factory=list)
    evolves_from: int = 0

    @property
    def bst(self) -> int:
        return sum(self.stats)

    @property
    def legendary(self) -> bool:
        return self.id in LEGENDARIES

    @property
    def basic(self) -> bool:
        return self.evolves_from == 0

    @property
    def fully_evolved(self) -> bool:
        return not self.evolves_to


def make_rng(seed_text: str) -> tuple[random.Random, str]:
    if not seed_text.strip():
        seed_text = str(int.from_bytes(os.urandom(4), "little"))
    digest = hashlib.sha256(seed_text.strip().encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "little")), seed_text.strip()


class Log:
    """Registro de cambios (spoiler) y de avisos para la interfaz."""

    def __init__(self, emit: Callable[[str], None] | None = None):
        self.sections: dict[str, list[str]] = {}
        self.emit = emit or (lambda m: None)

    def info(self, msg: str) -> None:
        self.emit(msg)

    def add(self, section: str, line: str) -> None:
        self.sections.setdefault(section, []).append(line)

    def render(self, header: str) -> str:
        out = [header, ""]
        for sec, lines in self.sections.items():
            out.append(f"===== {sec} =====")
            out.extend(lines)
            out.append("")
        return "\n".join(out)


class Picker:
    """Elige especies de reemplazo respetando los ajustes."""

    def __init__(self, species: dict[int, Species], rng: random.Random, max_id: int,
                 generations: Iterable[int] = ()):
        self.sp = species
        self.rng = rng
        gens = set(generations)
        self.all = sorted(s.id for s in species.values()
                          if 0 < s.id <= max_id and s.in_game and s.bst > 0
                          and (not gens or generation_of(s.id) in gens))
        if not self.all:  # filtro demasiado estricto: se ignora
            self.all = sorted(s.id for s in species.values() if 0 < s.id <= max_id and s.in_game and s.bst > 0)

    def pool(self, legendaries: bool, restrict: Iterable[int] | None = None,
             extra: Callable[[Species], bool] | None = None) -> list[int]:
        base = self.all if restrict is None else [i for i in restrict if i in self.sp]
        out = [i for i in base
               if (legendaries or not self.sp[i].legendary)
               and (extra is None or extra(self.sp[i]))]
        return out or list(base) or list(self.all)

    def pick(self, original: int, mode: str, pool: list[int], avoid: set[int] | None = None) -> int:
        if mode == S.UNCHANGED or not pool:
            return original
        cands = pool
        if avoid:
            cands = [c for c in pool if c not in avoid] or pool
        if mode == S.SIMILAR and original in self.sp and self.sp[original].bst > 0:
            target = self.sp[original].bst
            for pct in (0.10, 0.15, 0.25, 0.40, 1.0):
                near = [c for c in cands if abs(self.sp[c].bst - target) <= target * pct]
                if len(near) >= 5 or pct == 1.0:
                    if near:
                        cands = near
                    break
        return self.rng.choice(cands)

    def family_root(self, sid: int) -> int:
        seen = set()
        while sid in self.sp and self.sp[sid].evolves_from and sid not in seen:
            seen.add(sid)
            sid = self.sp[sid].evolves_from
        return sid

    def families(self) -> list[list[int]]:
        """Familias evolutivas (raíz primero), para 'seguir evoluciones'."""
        done: set[int] = set()
        fams = []
        for sid in sorted(self.sp):
            root = self.family_root(sid)
            if root in done:
                continue
            fam, stack = [], [root]
            while stack:
                cur = stack.pop(0)
                if cur in done or cur not in self.sp:
                    continue
                done.add(cur)
                fam.append(cur)
                stack.extend(self.sp[cur].evolves_to)
            fams.append(fam)
        return fams

    def evolve_for_level(self, sid: int, level: int, threshold: int) -> int:
        """Si threshold>0 y el nivel lo supera, sube a la última evolución."""
        if threshold <= 0 or level < threshold:
            return sid
        seen = set()
        while sid in self.sp and self.sp[sid].evolves_to and sid not in seen:
            seen.add(sid)
            sid = self.rng.choice(self.sp[sid].evolves_to)
        return sid


class FileStore:
    """Lee del romfs original (solo lectura) y guarda en memoria lo modificado."""

    def __init__(self, romfs: Path):
        self.romfs = Path(romfs)
        self.changed: dict[str, bytes] = {}

    def path(self, rel: str) -> Path:
        return self.romfs / rel

    def exists(self, rel: str) -> bool:
        return rel in self.changed or self.path(rel).is_file()

    def read(self, rel: str) -> bytearray:
        if rel in self.changed:
            return bytearray(self.changed[rel])
        return bytearray(self.path(rel).read_bytes())

    def write(self, rel: str, data: bytes) -> None:
        self.changed[rel.replace("\\", "/")] = bytes(data)

    def glob(self, rel_dir: str, pattern: str) -> list[str]:
        base = self.path(rel_dir)
        if not base.is_dir():
            return []
        return sorted(f"{rel_dir}/{p.name}" for p in base.glob(pattern) if p.is_file())

    def flush(self, out_romfs: Path) -> int:
        for rel, data in self.changed.items():
            dst = Path(out_romfs) / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
        return len(self.changed)
