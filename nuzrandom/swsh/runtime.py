"""Combate oculto en Espada/Escudo: el Pokémon que ves en el mapa no es el que combates.

Los archivos del romfs no pueden separar el modelo del mapa del Pokémon del combate:
los dos salen del mismo hueco de la tabla. Esto lo hace un módulo ExLaunch que se
carga con el juego (exefs/subsdk9) y cambia la especie justo al empezar el combate.

El módulo es el de PokeFeur Randomizer SWSH (GPLv3), basado en swsh-mods-exl de
Lincoln-LM. NuzRandom no lo incluye: lo copia de la carpeta de PokeFeur que tenga
el usuario. Lee su configuración de sdcard/config/swsh-mods-exl/config.toml.
Solo funciona con la versión 1.3.2 del juego.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

MANAGED = "# Managed-by: NuzRandom"
CONFIG_REL = Path("config") / "swsh-mods-exl" / "config.toml"
MODES = {"cada_combate": "random", "zona": "zone", "global": "global"}
FOLDER_NAMES = ("PokeFeurRandomSWSH", "PokeFeurRandomSWSH-main", "PokeFeur")


def _module_dirs(base: Path, title_id: str) -> list[Path]:
    """Acepta la carpeta de PokeFeur, su assets/exlaunch o la carpeta del juego."""
    return [base / "assets" / "exlaunch" / title_id, base / "exlaunch" / title_id, base / title_id, base]


def default_search_dirs() -> list[Path]:
    """Carpetas de PokeFeur junto a la de NuzRandom."""
    import sys
    app = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    out = []
    for parent in (app, app.parent):
        out += [parent / n for n in FOLDER_NAMES]
    return out


def find_module(folder: str, title_id: str, emulator: str | None) -> tuple[Path, Path]:
    """Devuelve (subsdk9, main.npdm) de la variante adecuada para el emulador."""
    variant = "_ryujinx" if emulator == "Ryujinx" else "_stable"
    bases = [Path(folder)] if folder.strip() else default_search_dirs()
    for base in bases:
        for d in _module_dirs(base, title_id):
            for suffix in (variant, ""):
                sub, npdm = d / f"subsdk9{suffix}", d / f"main.npdm{suffix}"
                if sub.is_file() and npdm.is_file():
                    return sub, npdm
    where = folder.strip() or ", ".join(str(b) for b in bases[:2])
    raise RuntimeError(
        "El combate oculto necesita el módulo de PokeFeur Randomizer SWSH y no lo encuentro en: " + where + ".\n"
        "Descarga https://github.com/JonatanUHC/PokeFeurRandomSWSH y elige su carpeta en la pestaña Salvajes "
        "(«Carpeta de PokeFeur»), o desactiva el combate oculto.")


def sdmc_dir(emulator: str | None) -> Path | None:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    if emulator == "Ryujinx":
        return appdata / "Ryujinx" / "sdcard"
    if emulator and emulator.startswith("Yuzu"):
        return appdata / "yuzu" / "sdmc"
    return None


def seed_u64(seed: str) -> int:
    # TOML solo admite enteros con signo de 64 bits.
    return int.from_bytes(hashlib.sha256(("combate:" + seed).encode("utf-8")).digest()[:8], "little") & (2**63 - 1)


def config_text(mode: str, battle_pool: list[int], seed: str) -> str:
    """config.toml con solo el combate oculto activo; el resto del módulo apagado."""
    pool = ", ".join(str(s) for s in battle_pool)
    off = ["overworld_shiny", "underworld", "camera_tweaks", "uncap_level", "freecam", "glimwood_overworld",
           "synchro_mode", "extended_following", "fishing_tweaks", "dex_animations", "exp_level_cap",
           "exp_runtime", "runtime_pc", "runtime_status", "early_bike"]
    lines = [MANAGED, "# Generado por NuzRandom para el módulo ExLaunch de PokeFeur (swsh-mods-exl).",
             "# Se reescribe cada vez que pulsas Randomizar.", ""]
    for sec in off:
        lines += [f"[{sec}]", "active = false", ""]
    lines += ["[exp_share]", "enabled = true", "",
              "[randomizer]", "active = true",
              '# Lo que ves en el mapa sale de las tablas del mod; lo que combates lo elige el módulo.',
              'visible_mode = "vanilla"', f'battle_mode = "{MODES.get(mode, "random")}"',
              "visible_pool = []", f"battle_pool = [{pool}]", "reset_discoveries = false",
              f"seed = {seed_u64(seed)}", ""]
    return "\n".join(lines)


def install_config(sdmc: Path, text: str) -> Path:
    """Escribe el config.toml. Si había uno de otra herramienta, guarda una copia antes."""
    path = sdmc / CONFIG_REL
    if path.is_file() and MANAGED not in path.read_text(encoding="utf-8", errors="replace"):
        backup = path.with_name("config.toml.antes_de_nuzrandom")
        if not backup.exists():
            shutil.copy2(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def remove_config(sdmc: Path) -> bool:
    """Quita el config.toml solo si lo escribió NuzRandom."""
    path = sdmc / CONFIG_REL
    if path.is_file() and MANAGED in path.read_text(encoding="utf-8", errors="replace"):
        path.unlink()
        return True
    return False


def copy_module(sub: Path, npdm: Path, mod_root: Path) -> None:
    exefs = mod_root / "exefs"
    exefs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sub, exefs / "subsdk9")
    shutil.copy2(npdm, exefs / "main.npdm")
