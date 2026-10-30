"""Ajustes del randomizer. Se guardan/cargan como JSON para poder repetir una partida."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields

# Modos de elección de especie
UNCHANGED = "sin_cambios"
RANDOM = "aleatorio"
SIMILAR = "fuerza_similar"   # total de estadísticas base parecido (±10 %, se amplía si hay pocos)
CUSTOM = "personalizado"      # solo starters
TYPE_THEME = "tematico_tipo"  # entrenadores: un tipo por equipo
SAME_AS_TRAINERS = "igual_que_entrenadores"

SPECIES_MODES = [UNCHANGED, RANDOM, SIMILAR]


@dataclass
class Settings:
    # --- General ---
    seed: str = ""
    spoiler_log: bool = True
    generation_filter: list = field(default_factory=list)  # vacío = todas

    # --- Pokémon salvajes ---
    wild_mode: str = RANDOM
    wild_mapping: str = "zona"          # hueco | zona | global | uno_por_zona
    wild_legendaries: bool = False
    wild_level_percent: int = 0
    wild_overworld: bool = True
    wild_min_bst: int = 0
    wild_max_bst: int = 0               # 0 = sin límite
    wild_held_items_random: bool = False

    # --- Encuentros fijos ---
    static_mode: str = RANDOM
    static_legendaries: bool = False
    static_keep_story_legendaries: bool = True

    # --- Starters, regalos e intercambios ---
    starter_mode: str = RANDOM
    starter_custom: list = field(default_factory=lambda: ["", "", ""])
    starter_basic_only: bool = True
    starter_three_stages: bool = False
    starter_distinct_types: bool = True
    starter_type_triangle: bool = False
    starter_legendaries: bool = False
    gift_mode: str = RANDOM
    trade_mode: str = RANDOM
    gift_legendaries: bool = False

    # --- Entrenadores normales ---
    trainer_mode: str = SIMILAR          # + TYPE_THEME
    trainer_legendaries: bool = False
    trainer_level_percent: int = 0
    trainer_levelup_moves: bool = True
    trainer_force_evolved_level: int = 0
    trainer_max_ai: bool = False
    trainer_perfect_ivs: bool = False
    trainer_random_natures: bool = False
    trainer_no_duplicates: bool = True

    # --- Jefes (gimnasios, rivales, villanos, campeón) ---
    boss_full_teams: bool = True
    boss_include_first_rival: bool = False
    boss_mode: str = SAME_AS_TRAINERS
    boss_legendaries: bool = False
    boss_level_percent: int = 0
    boss_min_bst: int = 0
    boss_force_evolved_level: int = 30
    boss_max_ai: bool = True
    boss_perfect_ivs: bool = False
    boss_held_items: bool = False
    boss_extra_ids: str = ""             # IDs de entrenador que también cuentan como jefes
    boss_excluded_ids: str = ""          # IDs que NO deben contar como jefes

    # --- Datos de los Pokémon ---
    types_mode: str = UNCHANGED
    abilities_mode: str = UNCHANGED
    abilities_wonder_guard: bool = False
    stats_mode: str = UNCHANGED           # sin_cambios | mezclar | redistribuir
    follow_evolutions: bool = True
    min_catch_rate: int = 45
    exp_curve: str = UNCHANGED            # sin_cambios | rapida | media | lenta
    exp_yield_percent: int = 100

    # --- Movimientos ---
    learnset_mode: str = UNCHANGED
    learnset_damaging_first: bool = True
    learnset_stab_percent: int = 40
    tm_moves_mode: str = UNCHANGED
    tm_compat_mode: str = UNCHANGED       # sin_cambios | aleatorio | todos
    move_data_random: bool = False
    move_power: bool = True
    move_accuracy: bool = True
    move_pp: bool = True
    move_type: bool = False
    ban_ohko: bool = True

    # --- Evoluciones ---
    evo_easy: bool = True                 # intercambio/amistad -> nivel
    evo_easy_level: int = 30
    evo_special_to_level: bool = True     # métodos raros (giros, críticos, lluvia…) -> nivel
    evo_level_mode: str = "tope"          # sin_cambios | tope | porcentaje
    evo_level_cap: int = 36
    evo_level_percent: int = 75
    evo_mode: str = UNCHANGED

    # --- Objetos y tiendas ---
    shop_price_percent: int = 25          # 100 = precios originales
    shop_keep_valuables: bool = True
    mart_max_repel: bool = True
    mart_rare_candy: bool = True
    rare_candy_price: int = 1
    mart_extra_items: str = ""
    shops_secondary_random: bool = True
    shops_tm_random: bool = True
    shops_evo_percent: int = 30
    field_items_random: bool = True
    hidden_items_random: bool = True
    gift_items_random: bool = True
    items_include_tms: bool = True
    items_evo_percent: int = 15
    items_exclude: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Settings":
        raw = json.loads(text)
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})


def nuzlocke_preset() -> Settings:
    """Nuzlocke clásico: todo aleatorio pero justo, jefes con equipos completos."""
    return Settings()


def hard_preset() -> Settings:
    s = Settings(trainer_level_percent=10, boss_level_percent=15, trainer_max_ai=True, boss_perfect_ivs=True,
                 boss_min_bst=450, boss_held_items=True, trainer_random_natures=True, min_catch_rate=0,
                 rare_candy_price=200, shop_price_percent=50)
    return s


def chaos_preset() -> Settings:
    return Settings(wild_mode=RANDOM, wild_mapping="hueco", trainer_mode=RANDOM, types_mode=RANDOM,
                    abilities_mode=RANDOM, stats_mode="redistribuir", learnset_mode=RANDOM, tm_moves_mode=RANDOM,
                    tm_compat_mode=RANDOM, move_data_random=True, evo_mode=RANDOM, wild_legendaries=True,
                    trainer_legendaries=True, static_legendaries=True)


def encounters_only_preset() -> Settings:
    return Settings(trainer_mode=UNCHANGED, boss_full_teams=False, boss_force_evolved_level=0, boss_max_ai=False,
                    min_catch_rate=0, evo_easy=False, evo_special_to_level=False, evo_level_mode=UNCHANGED,
                    shop_price_percent=100, mart_max_repel=False, mart_rare_candy=False,
                    shops_secondary_random=False, shops_tm_random=False, field_items_random=False,
                    hidden_items_random=False, gift_items_random=False)


PRESETS = {
    "Nuzlocke clásico (recomendado)": nuzlocke_preset,
    "Nuzlocke difícil": hard_preset,
    "Caos total": chaos_preset,
    "Solo encuentros": encounters_only_preset,
}
