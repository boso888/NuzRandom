"""Interfaz de escritorio (Tkinter, incluido en Python para Windows)."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__, engine, settings as S

CONFIG_FILE = Path(os.environ.get("APPDATA", Path.home())) / "NuzRandom" / "ultima_config.json"

MODE_LABELS = {
    S.UNCHANGED: "Sin cambios", S.RANDOM: "Aleatorio", S.SIMILAR: "Fuerza similar",
    S.CUSTOM: "Elegidos por mí", S.TYPE_THEME: "Temático (un tipo por equipo)",
    S.SAME_AS_TRAINERS: "Igual que los entrenadores normales",
    "hueco": "Cada hueco por separado", "zona": "Igual en toda la zona (recomendado)",
    "global": "Igual en todo el juego", "uno_por_zona": "Una sola especie por zona",
    "mezclar": "Mezclar", "redistribuir": "Redistribuir (mismo total)",
    "todos": "Todos aprenden todo", "rapida": "Rápida", "media": "Media", "lenta": "Lenta",
    "tope": "Nivel máximo", "porcentaje": "Porcentaje del nivel original",
}

TAB_INTRO = {
    "Salvajes": "Qué Pokémon aparecen en hierba, agua, cuevas y en el mapa. Para nuzlocke se recomienda "
                "'Igual en toda la zona': cada especie de una zona se cambia siempre por la misma.",
    "Starters y regalos": "Tu primer Pokémon, los que te regalan, los intercambios con NPC y los encuentros fijos "
                          "(Pokémon quietos en el mapa o de la historia).",
    "Entrenadores": "Todos los entrenadores del juego que NO son jefes. Mantienen el número de Pokémon original.",
    "Jefes": "Combates importantes: líderes de gimnasio, rivales, villanos y campeón. Aquí puedes hacerlos de 6 "
             "Pokémon y más duros sin tocar al resto de entrenadores.",
    "Pokémon": "Cambia los datos de las especies: tipos, habilidades, estadísticas, captura y experiencia.",
    "Movimientos": "Movimientos que se aprenden por nivel, contenido de las MT/DT y datos de los movimientos.",
    "Evoluciones": "Haz que evolucionar sea más fácil en un nuzlocke sin intercambios ni amistad.",
    "Objetos y tiendas": "Precios, tienda principal, tiendas secundarias y de MT, objetos del suelo y regalados. "
                         "Los objetos clave de la historia nunca se tocan.",
}

# (pestaña, grupo, etiqueta, atributo, tipo, opciones, ayuda)
F = []


def opt(tab, group, label, attr, kind, opts=None, help_=""):
    F.append((tab, group, label, attr, kind, opts, help_))


opt("Salvajes", "Especies", "Pokémon salvajes", "wild_mode", "combo", S.SPECIES_MODES,
    "Aleatorio: cualquier especie. Fuerza similar: una especie con estadísticas totales parecidas a la original, "
    "para que la dificultad de cada zona se mantenga.")
opt("Salvajes", "Especies", "Coherencia", "wild_mapping", "combo", ["hueco", "zona", "global", "uno_por_zona"],
    "Igual en toda la zona: un Pidgey de la Ruta 1 siempre se convierte en el mismo Pokémon en esa ruta.\n"
    "Igual en todo el juego: el cambio se mantiene en todas las zonas.\n"
    "Una sola especie por zona: cada zona tiene un único Pokémon posible (nuzlocke muy restringido).")
opt("Salvajes", "Especies", "Permitir legendarios", "wild_legendaries", "check", None,
    "Si se activa, pueden aparecer legendarios y singulares como Pokémon salvajes.")
opt("Salvajes", "Especies", "Incluir los visibles en el mapa (Espada/Escudo)", "wild_overworld", "check", None,
    "Los Pokémon que caminan por el mapa. Solo se usan especies que el juego ya sabe mostrar fuera, para evitar "
    "cuelgues.")
opt("Salvajes", "Filtros", "Total de estadísticas mínimo (0 = sin límite)", "wild_min_bst", "spin", (0, 720),
    "Evita Pokémon demasiado débiles. Ejemplo: 300 elimina Magikarp, Caterpie…")
opt("Salvajes", "Filtros", "Total de estadísticas máximo (0 = sin límite)", "wild_max_bst", "spin", (0, 720),
    "Evita Pokémon demasiado fuertes al principio. Ejemplo: 500 quita pseudolegendarios.")
opt("Salvajes", "Filtros", "Niveles salvajes (± %)", "wild_level_percent", "spin", (-50, 100),
    "Sube o baja el nivel de todos los Pokémon salvajes. 20 = un 20 % más de nivel.")
opt("Salvajes", "Filtros", "Objetos equipados aleatorios en salvajes", "wild_held_items_random", "check", None,
    "Los Pokémon salvajes llevan objetos aleatorios (útil con Ladrón o Covet).")

opt("Starters y regalos", "Starters", "Starters", "starter_mode", "combo", [S.UNCHANGED, S.RANDOM, S.SIMILAR, S.CUSTOM],
    "Elegidos por mí: escribe abajo el nombre o número de los tres Pokémon.")
opt("Starters y regalos", "Starters", "Starter 1 (nombre o número)", "starter_custom.0", "entry", None,
    "Por ejemplo: Charmander, 4 o Totodile. Solo se usa con 'Elegidos por mí'.")
opt("Starters y regalos", "Starters", "Starter 2", "starter_custom.1", "entry", None, "")
opt("Starters y regalos", "Starters", "Starter 3", "starter_custom.2", "entry", None, "")
opt("Starters y regalos", "Starters", "Solo Pokémon sin evolucionar que puedan evolucionar", "starter_basic_only", "check", None,
    "Evita que te toque un Pokémon ya evolucionado o uno que no evoluciona nunca.")
opt("Starters y regalos", "Starters", "Solo líneas de 3 fases", "starter_three_stages", "check", None,
    "Como los starters de verdad: el Pokémon evoluciona dos veces.")
opt("Starters y regalos", "Starters", "Los tres sin tipos en común", "starter_distinct_types", "check", None, "")
opt("Starters y regalos", "Starters", "Triángulo Planta / Fuego / Agua", "starter_type_triangle", "check", None,
    "El primero tendrá tipo Planta, el segundo Fuego y el tercero Agua.")
opt("Starters y regalos", "Starters", "Permitir starters legendarios", "starter_legendaries", "check", None, "")
opt("Starters y regalos", "Regalos e intercambios", "Pokémon regalados", "gift_mode", "combo", S.SPECIES_MODES,
    "Pokémon que te dan los NPC (por ejemplo, Toxel). Los legendarios regalados no se tocan.")
opt("Starters y regalos", "Regalos e intercambios", "Intercambios con NPC", "trade_mode", "combo", S.SPECIES_MODES, "")
opt("Starters y regalos", "Regalos e intercambios", "Permitir legendarios en regalos/intercambios", "gift_legendaries", "check", None, "")
opt("Starters y regalos", "Encuentros fijos", "Encuentros fijos", "static_mode", "combo", S.SPECIES_MODES,
    "Pokémon quietos en el mapa o de eventos de la historia.")
opt("Starters y regalos", "Encuentros fijos", "Permitir legendarios", "static_legendaries", "check", None, "")
opt("Starters y regalos", "Encuentros fijos", "No tocar los legendarios de la historia", "static_keep_story_legendaries", "check", None,
    "Recomendado: cambiar a Eternatus o a los lobos legendarios puede romper escenas de la historia.")

opt("Entrenadores", "Equipos", "Especies", "trainer_mode", "combo", [S.UNCHANGED, S.RANDOM, S.SIMILAR, S.TYPE_THEME],
    "Fuerza similar mantiene la dificultad. Temático: cada entrenador usa un único tipo al azar.")
opt("Entrenadores", "Equipos", "Permitir legendarios", "trainer_legendaries", "check", None, "")
opt("Entrenadores", "Equipos", "Sin especies repetidas en un equipo", "trainer_no_duplicates", "check", None, "")
opt("Entrenadores", "Equipos", "Evolucionar del todo a partir del nivel (0 = no)", "trainer_force_evolved_level", "spin", (0, 100),
    "Ejemplo: 40 hace que a partir de nivel 40 los Pokémon rivales estén en su última evolución.")
opt("Entrenadores", "Dificultad", "Niveles (± %)", "trainer_level_percent", "spin", (-50, 100),
    "Se aplica a todos los entrenadores, también a los jefes.")
opt("Entrenadores", "Dificultad", "Movimientos según el nivel", "trainer_levelup_moves", "check", None,
    "Al cambiar la especie, el Pokémon usa los 4 últimos movimientos que aprendería a su nivel.")
opt("Entrenadores", "Dificultad", "IA al máximo", "trainer_max_ai", "check", None, "Los entrenadores eligen mejor sus ataques.")
opt("Entrenadores", "Dificultad", "IV perfectos", "trainer_perfect_ivs", "check", None, "")
opt("Entrenadores", "Dificultad", "Naturalezas aleatorias", "trainer_random_natures", "check", None, "")

opt("Jefes", "Equipos", "Equipos completos de 6 Pokémon", "boss_full_teams", "check", None,
    "Líderes, rivales, villanos y campeón llevarán 6 Pokémon. El resto de entrenadores conserva su número original.")
opt("Jefes", "Equipos", "Incluir el primer combate contra el rival", "boss_include_first_rival", "check", None,
    "El primer combate es a nivel 5 justo tras elegir starter. Con 6 Pokémon es casi imposible: desactivado por defecto.")
opt("Jefes", "Equipos", "Especies de los jefes", "boss_mode", "combo",
    [S.SAME_AS_TRAINERS, S.UNCHANGED, S.RANDOM, S.SIMILAR, S.TYPE_THEME], "")
opt("Jefes", "Equipos", "Permitir legendarios", "boss_legendaries", "check", None, "")
opt("Jefes", "Equipos", "Total de estadísticas mínimo (0 = sin límite)", "boss_min_bst", "spin", (0, 720),
    "Ejemplo: 450 hace que los jefes solo usen Pokémon fuertes.")
opt("Jefes", "Equipos", "Evolucionar del todo a partir del nivel (0 = no)", "boss_force_evolved_level", "spin", (0, 100), "")
opt("Jefes", "Dificultad", "Niveles extra para jefes (± %)", "boss_level_percent", "spin", (-50, 100),
    "Se suma al porcentaje de los entrenadores normales.")
opt("Jefes", "Dificultad", "IA al máximo", "boss_max_ai", "check", None, "")
opt("Jefes", "Dificultad", "IV perfectos", "boss_perfect_ivs", "check", None, "")
opt("Jefes", "Dificultad", "Objetos de combate equipados", "boss_held_items", "check", None,
    "Restos, Cinta Elección, Banda Focus… al azar.")
opt("Jefes", "Avanzado", "Añadir jefes (IDs de entrenador, ej. 12, 40-42)", "boss_extra_ids", "entry", None,
    "Para tratar como jefe a cualquier otro entrenador. Los IDs aparecen en el registro de cambios.")
opt("Jefes", "Avanzado", "Quitar jefes (IDs)", "boss_excluded_ids", "entry", None, "")

opt("Pokémon", "Especies", "Tipos", "types_mode", "combo", [S.UNCHANGED, S.RANDOM], "")
opt("Pokémon", "Especies", "Habilidades", "abilities_mode", "combo", [S.UNCHANGED, S.RANDOM], "")
opt("Pokémon", "Especies", "Permitir Superguarda", "abilities_wonder_guard", "check", None,
    "Superguarda hace inmune a todo menos a los ataques súper eficaces. Muy rota.")
opt("Pokémon", "Especies", "Estadísticas base", "stats_mode", "combo", [S.UNCHANGED, "mezclar", "redistribuir"],
    "Mezclar: intercambia las 6 estadísticas entre sí. Redistribuir: reparte el mismo total de otra forma.")
opt("Pokémon", "Especies", "Coherencia en la línea evolutiva", "follow_evolutions", "check", None,
    "Charmander, Charmeleon y Charizard reciben los mismos tipos, habilidades y reparto de estadísticas.")
opt("Pokémon", "Captura y experiencia", "Ratio de captura mínimo (0-255)", "min_catch_rate", "spin", (0, 255),
    "Más alto = más fácil de capturar. 45 es el de un starter; 255 el de un Caterpie.")
opt("Pokémon", "Captura y experiencia", "Curva de experiencia", "exp_curve", "combo", [S.UNCHANGED, "rapida", "media", "lenta"],
    "Rápida: todos suben de nivel con menos experiencia.")
opt("Pokémon", "Captura y experiencia", "Experiencia obtenida (%)", "exp_yield_percent", "spin", (10, 500),
    "100 = normal. 150 = un 50 % más de experiencia por combate.")

opt("Movimientos", "Por nivel", "Movimientos por nivel", "learnset_mode", "combo", [S.UNCHANGED, S.RANDOM],
    "Se conservan los niveles; cambia qué movimiento se aprende en cada uno.")
opt("Movimientos", "Por nivel", "Primer movimiento siempre de daño", "learnset_damaging_first", "check", None,
    "Evita empezar con un Pokémon que solo sabe Gruñido.")
opt("Movimientos", "Por nivel", "Movimientos de su tipo (%)", "learnset_stab_percent", "spin", (0, 100),
    "Probabilidad de que cada movimiento nuevo sea del mismo tipo que el Pokémon.")
opt("Movimientos", "Por nivel", "Prohibir fulminantes (Fisura, Guillotina…)", "ban_ohko", "check", None, "")
opt("Movimientos", "MT y DT", "Movimientos de las MT/DT", "tm_moves_mode", "combo", [S.UNCHANGED, S.RANDOM], "")
opt("Movimientos", "MT y DT", "Compatibilidad con MT/DT", "tm_compat_mode", "combo", [S.UNCHANGED, S.RANDOM, "todos"],
    "Aleatorio da más probabilidad a las MT del tipo del Pokémon.")
opt("Movimientos", "Datos", "Aleatorizar datos de movimientos", "move_data_random", "check", None, "")
opt("Movimientos", "Datos", "   · potencia", "move_power", "check", None, "")
opt("Movimientos", "Datos", "   · precisión", "move_accuracy", "check", None, "")
opt("Movimientos", "Datos", "   · PP", "move_pp", "check", None, "")
opt("Movimientos", "Datos", "   · tipo", "move_type", "check", None, "")

opt("Evoluciones", "Facilitar", "Intercambio y amistad → subir de nivel", "evo_easy", "check", None,
    "Machoke, Haunter, Golbat, Eevee… evolucionan al llegar al nivel de abajo.")
opt("Evoluciones", "Facilitar", "Nivel para esas evoluciones", "evo_easy_level", "spin", (2, 100), "")
opt("Evoluciones", "Facilitar", "Métodos raros → subir de nivel", "evo_special_to_level", "check", None,
    "Girar con Milcery, golpes críticos de Farfetch'd, lluvia de Sliggoo, saber un movimiento, equipo… pasan a nivel.")
opt("Evoluciones", "Adelantar", "Evoluciones tardías", "evo_level_mode", "combo", [S.UNCHANGED, "tope", "porcentaje"],
    "Nivel máximo: ninguna evolución por nivel ocurre más tarde del nivel indicado.\n"
    "Porcentaje: todas las evoluciones por nivel ocurren antes, proporcionalmente.")
opt("Evoluciones", "Adelantar", "Nivel máximo", "evo_level_cap", "spin", (2, 100),
    "Ejemplo: 36 hace que Dreepy (Dragapult a nivel 60) llegue a su forma final a nivel 36.")
opt("Evoluciones", "Adelantar", "Porcentaje del nivel original", "evo_level_percent", "spin", (10, 100),
    "75 = un Pokémon que evolucionaba a nivel 40 lo hará a nivel 30.")
opt("Evoluciones", "Otros", "Evoluciones aleatorias", "evo_mode", "combo", S.SPECIES_MODES,
    "Cada Pokémon evoluciona en otra especie al azar.")

opt("Objetos y tiendas", "Precios", "Precio de los objetos (%)", "shop_price_percent", "spin", (1, 500),
    "25 = todo cuesta una cuarta parte. 100 = precios originales.")
opt("Objetos y tiendas", "Precios", "Mantener el valor de los objetos para vender", "shop_keep_valuables", "check", None,
    "Pepitas, Perlas, Polvoestelar… se siguen vendiendo caros.")
opt("Objetos y tiendas", "Tienda principal", "Repelente Máximo desde el principio", "mart_max_repel", "check", None,
    "La tienda principal no cambia: solo se añaden estos objetos al principio de la lista.")
opt("Objetos y tiendas", "Tienda principal", "Caramelos Raros a la venta", "mart_rare_candy", "check", None, "")
opt("Objetos y tiendas", "Tienda principal", "Precio del Caramelo Raro", "rare_candy_price", "spin", (1, 50000),
    "1 es el mínimo posible.")
opt("Objetos y tiendas", "Tienda principal", "Otros objetos a añadir (nombres o IDs)", "mart_extra_items", "entry", None,
    "Separados por comas. Ejemplo: Revivir, Hiperpoción, 1 (Master Ball).")
opt("Objetos y tiendas", "Otras tiendas", "Tiendas secundarias aleatorias", "shops_secondary_random", "check", None,
    "Boutiques, grandes almacenes, puestos… venden objetos al azar.")
opt("Objetos y tiendas", "Otras tiendas", "Tiendas de MT/DT aleatorias", "shops_tm_random", "check", None, "")
opt("Objetos y tiendas", "Otras tiendas", "Objetos de evolución en tiendas (%)", "shops_evo_percent", "spin", (0, 100),
    "Parte de los objetos de las tiendas secundarias que serán piedras y objetos de evolución.")
opt("Objetos y tiendas", "Objetos del mundo", "Objetos del suelo aleatorios", "field_items_random", "check", None,
    "Las Poké Balls que ves en el suelo. Los objetos clave de la historia se respetan.")
opt("Objetos y tiendas", "Objetos del mundo", "Objetos ocultos aleatorios", "hidden_items_random", "check", None,
    "Los brillos del suelo que solo ves al acercarte.")
opt("Objetos y tiendas", "Objetos del mundo", "Objetos regalados aleatorios", "gift_items_random", "check", None,
    "Lo que te dan los NPC y líderes. Bici, Recomendación, Brazalete Dinamax… nunca se tocan.")
opt("Objetos y tiendas", "Objetos del mundo", "Pueden salir MT/DT", "items_include_tms", "check", None, "")
opt("Objetos y tiendas", "Objetos del mundo", "Objetos de evolución (%)", "items_evo_percent", "spin", (0, 100), "")
opt("Objetos y tiendas", "Objetos del mundo", "Objetos que nunca deben salir", "items_exclude", "entry", None,
    "Nombres o IDs separados por comas. Ejemplo: Master Ball, Restos.")

GUIDE = """Bienvenido a NuzRandom

1.  Prepara tu copia limpia (solo una vez)
    En Ryujinx, haz clic derecho sobre tu juego → Extraer datos → RomFS y elige una carpeta,
    por ejemplo C:\\Pokemon\\Espada\\romfs. Esa carpeta es tu "ROM limpia": la app nunca la modifica.
    Espada y Escudo deben tener la actualización 1.3.2 instalada antes de extraer.

2.  Pestaña General
    • Elige la carpeta romfs. La app detecta el juego; si es Espada o Escudo, indica cuál.
    • Deja "Instalar directamente en: Ryujinx" para no tener que copiar nada a mano.
    • Elige un preajuste. "Nuzlocke clásico" ya incluye: jefes de 6 Pokémon, tienda barata con
      Repelente Máximo y Caramelos Raros, objetos aleatorios y evoluciones fáciles.

3.  Ajusta lo que quieras
    Cada pestaña empieza con una explicación. Pasa el ratón por encima de cualquier opción
    (o del símbolo ⓘ) para ver qué hace.

4.  Pulsa Randomizar
    En unos segundos tendrás el mod listo. Si escribiste una semilla, podrás repetir exactamente
    la misma partida o compartirla con tus amigos.

5.  Juega
    En Ryujinx: clic derecho en el juego → Administrar mods, comprueba que "NuzRandom" está activado
    y abre el juego. Empieza una partida nueva.

6.  Nuevo nuzlocke
    Vuelve a pulsar Randomizar (con otra semilla). El mod anterior se sustituye automáticamente
    y tu copia limpia sigue intacta.

¿Algo falla?  Pulsa "Diagnóstico" en la pestaña General y comparte el archivo diagnostico.txt.
El registro de cambios (spoiler) se guarda en la carpeta de salida: no lo abras si no quieres
saber qué te espera."""


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tip, self.job = widget, text, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _schedule(self, _e=None):
        self.job = self.widget.after(350, self._show)

    def _show(self):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, justify="left", wraplength=420, background="#FFFDE8",
                 relief="solid", borderwidth=1, padx=8, pady=6).pack()

    def _hide(self, _e=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class Scrollable(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=(14, 10))
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.bind_all("<MouseWheel>", self._wheel, add="+")
        self.bind_all("<Button-4>", lambda e: self._scroll(-1), add="+")
        self.bind_all("<Button-5>", lambda e: self._scroll(1), add="+")

    def _visible(self):
        try:
            return self.winfo_ismapped()
        except tk.TclError:
            return False

    def _wheel(self, e):
        if self._visible():
            self.canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")

    def _scroll(self, n):
        if self._visible():
            self.canvas.yview_scroll(n, "units")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"NuzRandom {__version__} · Randomizer para nuzlockes")
        self.geometry("1000x780")
        self.minsize(820, 620)
        self.vars: dict[str, tk.Variable] = {}
        self.msgs: queue.Queue = queue.Queue()
        self.last_result = None
        self._build()
        self._load_last()
        self.after(100, self._pump)

    # ----------------------------------------------------------- interfaz ---
    def _build(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Intro.TLabel", foreground="#444")
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"))
        style.configure("Ok.TLabel", foreground="#1a7f37")
        style.configure("Bad.TLabel", foreground="#b42318")
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        guide = Scrollable(self.nb)
        self.nb.add(guide, text="📖 Guía")
        ttk.Label(guide.inner, text=GUIDE, justify="left", font=("Segoe UI", 10)).pack(anchor="w")

        gen = Scrollable(self.nb)
        self.nb.add(gen, text="General")
        self._build_general(gen.inner)

        tabs: dict[str, tuple] = {}
        for tab, group, label, attr, kind, opts, help_ in F:
            if tab not in tabs:
                sc = Scrollable(self.nb)
                self.nb.add(sc, text=tab)
                ttk.Label(sc.inner, text=TAB_INTRO.get(tab, ""), wraplength=900, style="Intro.TLabel",
                          justify="left").pack(anchor="w", pady=(0, 8))
                tabs[tab] = (sc.inner, {})
            inner, groups = tabs[tab]
            if group not in groups:
                lf = ttk.LabelFrame(inner, text=group, padding=(10, 6))
                lf.pack(fill="x", pady=4)
                lf.columnconfigure(1, weight=1)
                groups[group] = [lf, 0]
            lf, row = groups[group]
            self._field(lf, row, label, attr, kind, opts, help_)
            groups[group][1] += 1

        bottom = ttk.Frame(self, padding=(8, 0, 8, 8))
        bottom.pack(fill="both")
        bar = ttk.Frame(bottom)
        bar.pack(fill="x")
        self.go = ttk.Button(bar, text="🎲  Randomizar", style="Big.TButton", command=self.start)
        self.go.pack(side="left", fill="x", expand=True, ipady=6)
        self.open_out = ttk.Button(bar, text="Abrir carpeta", command=self.open_folder)
        self.open_out.pack(side="left", padx=(6, 0), ipady=6)
        self.open_log = ttk.Button(bar, text="Ver registro", command=self.open_spoiler)
        self.open_log.pack(side="left", padx=(6, 0), ipady=6)
        self.progress = ttk.Progressbar(bottom, mode="indeterminate")
        self.progress.pack(fill="x", pady=(6, 0))
        self.out = tk.Text(bottom, height=6, wrap="word", state="disabled", font=("Consolas", 9))
        self.out.pack(fill="both", expand=True, pady=(6, 0))

    def _build_general(self, f):
        f.columnconfigure(1, weight=1)
        box = ttk.LabelFrame(f, text="1 · Tu juego", padding=10)
        box.pack(fill="x", pady=4)
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="Carpeta romfs").grid(row=0, column=0, sticky="w", pady=3)
        self.romfs = tk.StringVar()
        self.romfs.trace_add("write", lambda *_: self.after(200, self.check_romfs))
        ttk.Entry(box, textvariable=self.romfs).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(box, text="Elegir…", command=lambda: self._pick_dir(self.romfs)).grid(row=0, column=2)
        self.romfs_status = ttk.Label(box, text="Elige la carpeta que extrajiste de tu juego.")
        self.romfs_status.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(box, text="Juego").grid(row=2, column=0, sticky="w", pady=3)
        self.game = tk.StringVar(value="Espada")
        ttk.Combobox(box, textvariable=self.game, values=list(engine.GAMES), state="readonly").grid(
            row=2, column=1, sticky="w", padx=6)

        box = ttk.LabelFrame(f, text="2 · Dónde guardar el mod", padding=10)
        box.pack(fill="x", pady=4)
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="Carpeta de salida").grid(row=0, column=0, sticky="w", pady=3)
        self.outdir = tk.StringVar(value=str(Path.home() / "Documents" / "NuzRandom"))
        ttk.Entry(box, textvariable=self.outdir).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(box, text="Elegir…", command=lambda: self._pick_dir(self.outdir)).grid(row=0, column=2)
        ttk.Label(box, text="Instalar directamente en").grid(row=1, column=0, sticky="w", pady=3)
        self.emu = tk.StringVar(value="Ryujinx")
        cb = ttk.Combobox(box, textvariable=self.emu, values=["No instalar"] + list(engine.emulator_dirs()), state="readonly")
        cb.grid(row=1, column=1, sticky="w", padx=6)
        Tooltip(cb, "Copia el mod a la carpeta de mods del emulador. Solo tendrás que activarlo y jugar.")
        ttk.Label(box, text="Nombre del mod").grid(row=2, column=0, sticky="w", pady=3)
        self.modname = tk.StringVar(value="NuzRandom")
        ttk.Entry(box, textvariable=self.modname, width=24).grid(row=2, column=1, sticky="w", padx=6)

        box = ttk.LabelFrame(f, text="3 · Partida", padding=10)
        box.pack(fill="x", pady=4)
        ttk.Label(box, text="Preajuste").grid(row=0, column=0, sticky="w", pady=3)
        self.preset = tk.StringVar(value=list(S.PRESETS)[0])
        ttk.Combobox(box, textvariable=self.preset, values=list(S.PRESETS), state="readonly", width=34).grid(
            row=0, column=1, sticky="w", padx=6)
        ttk.Button(box, text="Aplicar preajuste", command=self.apply_preset).grid(row=0, column=2, sticky="w")
        ttk.Label(box, text="Semilla (vacío = al azar)").grid(row=1, column=0, sticky="w", pady=3)
        self.vars["seed"] = tk.StringVar()
        e = ttk.Entry(box, textvariable=self.vars["seed"], width=24)
        e.grid(row=1, column=1, sticky="w", padx=6)
        Tooltip(e, "Con la misma semilla y los mismos ajustes se obtiene exactamente el mismo juego.")
        self.vars["spoiler_log"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Guardar registro de cambios (spoiler)", variable=self.vars["spoiler_log"]).grid(
            row=2, column=1, sticky="w", padx=6, pady=3)
        ttk.Label(box, text="Generaciones permitidas").grid(row=3, column=0, sticky="w", pady=3)
        gens = ttk.Frame(box)
        gens.grid(row=3, column=1, columnspan=2, sticky="w", padx=6)
        self.gen_vars = []
        for g in range(1, 9):
            v = tk.BooleanVar(value=True)
            ttk.Checkbutton(gens, text=str(g), variable=v).pack(side="left")
            self.gen_vars.append(v)

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(10, 4))
        ttk.Button(btns, text="Guardar ajustes…", command=self.save_cfg).pack(side="left")
        ttk.Button(btns, text="Cargar ajustes…", command=self.load_cfg).pack(side="left", padx=6)
        ttk.Button(btns, text="Diagnóstico", command=self.diagnose).pack(side="left")

    def _field(self, frame, row, label, attr, kind, opts, help_):
        if kind == "check":
            v = tk.BooleanVar()
            w = ttk.Checkbutton(frame, text=label, variable=v)
            w.grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
        else:
            lab = ttk.Label(frame, text=label)
            lab.grid(row=row, column=0, sticky="w", pady=2, padx=(0, 10))
            if kind == "combo":
                v = tk.StringVar()
                w = ttk.Combobox(frame, textvariable=v, state="readonly", width=38,
                                 values=[MODE_LABELS.get(o, o) for o in opts])
            elif kind == "spin":
                v = tk.IntVar()
                w = ttk.Spinbox(frame, from_=opts[0], to=opts[1], textvariable=v, width=8)
            else:
                v = tk.StringVar()
                w = ttk.Entry(frame, textvariable=v, width=44)
            w.grid(row=row, column=1, sticky="w")
            if help_:
                Tooltip(lab, help_)
        if help_:
            Tooltip(w, help_)
            info = ttk.Label(frame, text="ⓘ", foreground="#2563eb", cursor="question_arrow")
            info.grid(row=row, column=2, sticky="w", padx=6)
            Tooltip(info, help_)
        self.vars[attr] = v

    # ------------------------------------------------- ajustes <-> widgets ---
    def apply(self, cfg: S.Settings):
        for tab, group, label, attr, kind, opts, help_ in F:
            v = self.vars[attr]
            if "." in attr:
                name, idx = attr.split(".")
                val = (list(getattr(cfg, name)) + ["", "", ""])[int(idx)]
            else:
                val = getattr(cfg, attr)
            v.set(MODE_LABELS.get(val, val) if kind == "combo" else val)
        self.vars["seed"].set(cfg.seed)
        self.vars["spoiler_log"].set(cfg.spoiler_log)
        for g, gv in enumerate(self.gen_vars, start=1):
            gv.set(not cfg.generation_filter or g in cfg.generation_filter)

    def collect(self) -> S.Settings:
        cfg = S.Settings()
        rev = {v: k for k, v in MODE_LABELS.items()}
        custom = ["", "", ""]
        for tab, group, label, attr, kind, opts, help_ in F:
            try:
                v = self.vars[attr].get()
            except (tk.TclError, ValueError):
                v = 0
            if kind == "combo":
                v = rev.get(v, v)
            if kind == "spin":
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    v = 0
            if "." in attr:
                custom[int(attr.split(".")[1])] = v
            else:
                setattr(cfg, attr, v)
        cfg.starter_custom = custom
        cfg.seed = self.vars["seed"].get()
        cfg.spoiler_log = bool(self.vars["spoiler_log"].get())
        gens = [g for g, gv in enumerate(self.gen_vars, start=1) if gv.get()]
        cfg.generation_filter = [] if len(gens) == 8 else gens
        return cfg

    def apply_preset(self):
        seed = self.vars["seed"].get()
        cfg = S.PRESETS[self.preset.get()]()
        cfg.seed = seed
        self.apply(cfg)
        self.log(f"Preajuste aplicado: {self.preset.get()}")

    def _state(self) -> dict:
        return {"romfs": self.romfs.get(), "game": self.game.get(), "outdir": self.outdir.get(),
                "emu": self.emu.get(), "modname": self.modname.get(), "preset": self.preset.get(),
                "settings": json.loads(self.collect().to_json())}

    def _load_last(self):
        self.apply(S.nuzlocke_preset())
        try:
            st = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            self.romfs.set(st.get("romfs", ""))
            self.game.set(st.get("game", "Espada"))
            self.outdir.set(st.get("outdir", self.outdir.get()))
            self.emu.set(st.get("emu", "Ryujinx"))
            self.modname.set(st.get("modname", "NuzRandom"))
            self.preset.set(st.get("preset", self.preset.get()))
            self.apply(S.Settings.from_json(json.dumps(st.get("settings", {}))))
        except (OSError, ValueError, TypeError):
            self.nb.select(0)

    def _save_last(self):
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps(self._state(), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def save_cfg(self):
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Ajustes", "*.json")])
        if p:
            Path(p).write_text(self.collect().to_json(), encoding="utf-8")

    def load_cfg(self):
        p = filedialog.askopenfilename(filetypes=[("Ajustes", "*.json")])
        if p:
            self.apply(S.Settings.from_json(Path(p).read_text(encoding="utf-8")))

    def _pick_dir(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if d:
            var.set(d)

    def check_romfs(self):
        p = self.romfs.get().strip()
        if not p:
            return
        try:
            fam = engine.detect_family(engine.normalize_romfs(Path(p)))
        except OSError:
            fam = None
        if fam == "swsh":
            self.romfs_status.configure(text="✔ Espada/Escudo detectado. Indica abajo cuál de los dos es.", style="Ok.TLabel")
            if self.game.get() not in ("Espada", "Escudo"):
                self.game.set("Espada")
        elif fam == "bdsp":
            self.romfs_status.configure(text="✔ Diamante Brillante/Perla Reluciente detectado. Indica cuál.", style="Ok.TLabel")
            if self.game.get() not in ("Diamante Brillante", "Perla Reluciente"):
                self.game.set("Diamante Brillante")
        else:
            self.romfs_status.configure(text="✖ No encuentro los datos del juego en esa carpeta. Debe contener "
                                             "'bin' (Espada/Escudo) o 'Data' (DPBP).", style="Bad.TLabel")

    # ------------------------------------------------------------ acciones ---
    def log(self, msg: str):
        self.msgs.put(msg)

    def _pump(self):
        while not self.msgs.empty():
            m = self.msgs.get()
            self.out.configure(state="normal")
            self.out.insert("end", m + "\n")
            self.out.see("end")
            self.out.configure(state="disabled")
        self.after(100, self._pump)

    def start(self):
        if not self.romfs.get():
            messagebox.showwarning("NuzRandom", "Elige primero la carpeta romfs de tu juego (pestaña General).")
            self.nb.select(1)
            return
        self._save_last()
        cfg = self.collect()
        emu = None if self.emu.get() == "No instalar" else self.emu.get()
        self.go.configure(state="disabled")
        self.progress.start(12)
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        self.out.configure(state="disabled")

        def work():
            try:
                res = engine.run(self.romfs.get(), self.game.get(), cfg, self.outdir.get(), emu,
                                 self.modname.get().strip() or "NuzRandom", emit=self.log)
                self.last_result = res
                self.log(f"\n¡Listo! Semilla: {res['seed']}.")
                if emu:
                    self.log(f"El mod ya está en {emu}. Ábrelo, comprueba que '{self.modname.get()}' está activado "
                             "en Administrar mods y empieza una partida nueva.")
                else:
                    self.log("Copia la carpeta del mod a la carpeta de mods de tu emulador.")
            except Exception as e:  # noqa: BLE001
                self.log("ERROR: " + str(e))
                self.log(traceback.format_exc())
            finally:
                self.after(0, self._done)

        threading.Thread(target=work, daemon=True).start()

    def _done(self):
        self.progress.stop()
        self.go.configure(state="normal")

    def _open(self, path):
        if not path or not Path(path).exists():
            messagebox.showinfo("NuzRandom", "Todavía no hay nada que abrir: pulsa Randomizar primero.")
            return
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def open_folder(self):
        self._open(self.outdir.get())

    def open_spoiler(self):
        self._open(self.last_result.get("log") if self.last_result else None)

    def diagnose(self):
        if not self.romfs.get():
            return
        self.log("Generando diagnóstico…")

        def work():
            try:
                romfs = engine.normalize_romfs(Path(self.romfs.get()))
                fam = engine.detect_family(romfs)
                lines = [f"NuzRandom {__version__}", f"romfs: {romfs}", f"detectado: {fam}"]
                if fam == "bdsp":
                    from .bdsp.randomizer import diagnose
                    lines.append(diagnose(romfs))
                elif fam == "swsh":
                    from .core import FileStore
                    from .swsh.randomizer import validate
                    from .swsh import items as IT
                    store = FileStore(romfs)
                    lines += validate(store) or ["Estructura básica de Espada/Escudo correcta."]
                    for rel in (IT.SHOP, IT.PLACEMENT, IT.ITEM_HASH):
                        lines.append(f"{rel}: {'sí' if store.exists(rel) else 'NO'}")
                    try:
                        from .core import FileStore as FS
                        from .swsh.formats import FB
                        invs = IT.shop_inventories(FB(FS(romfs).read(IT.SHOP)))
                        lines.append(f"inventarios de tienda reconocidos: {len(invs)}")
                    except Exception as e:  # noqa: BLE001
                        lines.append(f"tiendas: error {e}")
                out = Path(self.outdir.get()) / "diagnostico.txt"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text("\n".join(lines), encoding="utf-8")
                self.log(f"Diagnóstico guardado en {out}")
            except Exception as e:  # noqa: BLE001
                self.log("ERROR en diagnóstico: " + str(e))

        threading.Thread(target=work, daemon=True).start()


def main():
    App().mainloop()
