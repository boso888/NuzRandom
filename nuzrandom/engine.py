"""Orquestador: detecta el juego, ejecuta el randomizer y escribe la carpeta de mod."""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from . import __version__
from .core import FileStore, Log, make_rng
from .settings import Settings

GAMES = {
    "Espada": ("swsh", "0100ABF008968000"),
    "Escudo": ("swsh", "01008DB008C2C000"),
    "Diamante Brillante": ("bdsp", "0100000011D90000"),
    "Perla Reluciente": ("bdsp", "010018E011D92000"),
}
MARKER = "creado_por_nuzrandom.txt"


def normalize_romfs(path: Path) -> Path:
    """Acepta la carpeta romfs o una carpeta que la contenga."""
    path = Path(path)
    for cand in (path, path / "romfs", path / "RomFS"):
        if (cand / "bin").is_dir() or (cand / "Data").is_dir():
            return cand
    return path


def detect_family(romfs: Path) -> str | None:
    from .swsh import randomizer as sw
    from .bdsp import randomizer as bd
    if sw.detect(romfs):
        return "swsh"
    if (Path(romfs) / "Data").is_dir() and bd.detect(romfs):
        return "bdsp"
    return None


def emulator_dirs() -> dict[str, Path]:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return {
        "Ryujinx": appdata / "Ryujinx" / "mods" / "contents",
        "Yuzu / Suyu / Sudachi": appdata / "yuzu" / "load",
    }


def mod_target(base: Path, emulator: str, title_id: str, mod_name: str) -> Path:
    if emulator == "Ryujinx":
        return base / title_id / mod_name
    return base / title_id / mod_name


def _safe_clear(folder: Path) -> None:
    """Borra una carpeta de mod anterior SOLO si la creó esta app."""
    if folder.is_dir() and (folder / MARKER).is_file():
        shutil.rmtree(folder)


def run(romfs: str, game: str, cfg: Settings, out_dir: str, emulator: str | None, mod_name: str = "NuzRandom",
        emit=print) -> dict:
    romfs_path = normalize_romfs(Path(romfs))
    family, title_id = GAMES[game]
    found = detect_family(romfs_path)
    if found is None:
        raise RuntimeError("No reconozco esa carpeta como romfs de Espada/Escudo ni de DPBP.")
    if found != family:
        raise RuntimeError(f"La carpeta parece de otro juego ({'Espada/Escudo' if found == 'swsh' else 'DPBP'}).")

    rng, seed = make_rng(cfg.seed)
    log = Log(emit)
    store = FileStore(romfs_path)
    emit(f"Juego: {game} · semilla: {seed}")
    if family == "swsh":
        from .swsh.randomizer import SwShRandomizer, validate
        problems = validate(store)
        if problems:
            raise RuntimeError("\n".join(problems))
        SwShRandomizer(store, cfg, rng, log).run()
    else:
        from .bdsp.randomizer import BdspRandomizer
        BdspRandomizer(store, cfg, rng, log).run()

    targets = [Path(out_dir) / mod_name]
    if emulator and emulator in emulator_dirs():
        targets.append(mod_target(emulator_dirs()[emulator], emulator, title_id, mod_name))
    header = (f"NuzRandom {__version__} · {game} · semilla: {seed}\n"
              f"Generado: {datetime.now():%Y-%m-%d %H:%M}\n"
              f"Ajustes:\n{cfg.to_json()}")
    for t in targets:
        _safe_clear(t)
        n = store.flush(t / "romfs")
        (t / MARKER).write_text(f"Mod generado por NuzRandom. Semilla: {seed}\n", encoding="utf-8")
        emit(f"✔ {n} archivos escritos en {t}")
    log_path = None
    if cfg.spoiler_log:
        log_path = Path(out_dir) / f"spoiler_{mod_name}_{seed}.txt"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(log.render(header), encoding="utf-8")
        emit(f"✔ Registro de cambios: {log_path}")
    return {"seed": seed, "targets": [str(t) for t in targets], "log": str(log_path) if log_path else None,
            "files": len(store.changed)}
