# NuzRandom 0.2

Randomizer de escritorio para Windows pensado para **nuzlockes** en:

- **Pokémon Espada / Escudo** (versión 1.3.2)
- **Pokémon Diamante Brillante / Perla Reluciente** (experimental)

Lee la copia extraída de **tu propio juego** y genera un **mod LayeredFS** aparte. Tu copia nunca se modifica, así que cada nuzlocke parte de un juego limpio: vuelves a pulsar *Randomizar* y el mod anterior se sustituye.

> NuzRandom no incluye ni descarga ROMs, claves ni archivos de Nintendo. Necesitas tener el juego y volcarlo tú.

## Instalación

1. Instala **Python 3.10 o superior** desde python.org (marca *Add python.exe to PATH*).
2. Abre **`Iniciar.bat`**. La primera vez instala las dependencias y abre la app.
3. Opcional: **`Crear_EXE.bat`** genera `dist\NuzRandom.exe`, que no necesita Python.

Si ya tenías la versión 0.1, borra el archivo `.deps_ok` de la carpeta antes de abrir `Iniciar.bat`.

## Uso rápido

La app abre en la pestaña **📖 Guía**, que explica el proceso paso a paso. Cada pestaña empieza con una explicación, y cada opción tiene una ayuda (ⓘ) al pasar el ratón.

1. **General**: elige la carpeta romfs (la app detecta el juego), si quieres instalar el mod directamente en Ryujinx o Yuzu y un preajuste.
2. **Randomizar**.
3. En el emulador, activa el mod *NuzRandom* y empieza una partida nueva.

Preajustes: **Nuzlocke clásico** (recomendado), **Nuzlocke difícil**, **Caos total** y **Solo encuentros**.

## Qué incluye el preajuste Nuzlocke clásico

- **Jefes con 6 Pokémon**: líderes de gimnasio, Paul, Bede, Roxy, Olivia, Rose y Lionel. El resto de entrenadores conserva su número original de Pokémon.
- **Tienda**: todo al 25 % de su precio. La tienda principal no cambia salvo por el precio, y añade **Repelente Máximo** y **Caramelos Raros a 1 ₽** desde el principio.
- **Tiendas secundarias y de MT** con objetos aleatorios. El 30 % de los huecos de las secundarias son objetos de evolución.
- **Objetos del suelo, ocultos y regalados** completamente aleatorios. Los objetos clave de la historia (bici, Recomendación, Brazalete Dinamax…) nunca se tocan.
- **Evoluciones fáciles**: intercambio, amistad y métodos raros pasan a nivel 30, y ninguna evolución por nivel ocurre más tarde del nivel 36.
- Salvajes aleatorios iguales en toda la zona, starters, regalos, intercambios y encuentros fijos aleatorios, y entrenadores de fuerza similar.

## Todas las opciones

| Pestaña | Opciones |
|---|---|
| Salvajes | modo, coherencia (hueco / zona / todo el juego / una especie por zona), legendarios, visibles en el mapa, total de estadísticas mínimo y máximo, niveles ± %, objetos equipados |
| Starters y regalos | aleatorios / fuerza similar / elegidos por nombre, solo básicos, solo líneas de 3 fases, sin tipos repetidos, triángulo Planta-Fuego-Agua, legendarios; regalos, intercambios y encuentros fijos |
| Entrenadores | especies (aleatorio / similar / temático por tipo), legendarios, sin repetidos, evolución forzada desde un nivel, niveles ± %, movimientos según nivel, IA máxima, IV perfectos, naturalezas |
| Jefes | equipos de 6, primer combate contra el rival, modo propio, legendarios, total de estadísticas mínimo, evolución forzada, niveles extra, IA, IV, objetos de combate, añadir o quitar jefes por ID |
| Pokémon | tipos, habilidades (con o sin Superguarda), estadísticas (mezclar / redistribuir), coherencia evolutiva, ratio de captura mínimo, curva y cantidad de experiencia |
| Movimientos | por nivel (con primer ataque de daño y % del propio tipo), prohibir fulminantes, MT/DT y su compatibilidad, potencia, precisión, PP y tipo |
| Evoluciones | intercambio/amistad a nivel, métodos raros a nivel, nivel máximo o porcentaje, evoluciones aleatorias |
| Objetos y tiendas | % de precio, conservar objetos para vender, Repelente Máximo, Caramelos Raros y su precio, otros objetos para la tienda, tiendas secundarias y de MT, % de objetos de evolución, objetos del suelo, ocultos y regalados, MT en el mundo, lista de objetos prohibidos |
| General | semilla reproducible, generaciones permitidas, registro de cambios, guardar y cargar ajustes, diagnóstico |

## Diamante Brillante / Perla Reluciente

Funcionan: salvajes, entrenadores y jefes de 6, datos de Pokémon, movimientos, MT, evoluciones, precios, Repelente Máximo y Caramelos Raros en la tienda, y tiendas secundarias y de MT.

Pendiente: starters, regalos, encuentros fijos y objetos del suelo, que viven en los scripts del juego.

Los jefes se detectan por el tipo de entrenador. Revisa el registro y usa *Añadir jefes* si falta alguno.

## Limitaciones conocidas

- Probado con datos sintéticos que reproducen los formatos; **no con archivos reales del juego**. Si algo falla, pulsa **Diagnóstico** y comparte `diagnostico.txt`, que solo contiene nombres de campos.
- Espada/Escudo: los Pokémon visibles en el mapa solo usan especies que el juego original ya muestra fuera, para evitar cuelgues.
- El equipo de Paul no se adapta a los nuevos starters.
- Las evoluciones con varias ramas del mismo método (por ejemplo, Eevee por amistad) se quedan con la primera rama al pasar a nivel.

## Créditos y licencia

GPLv3. Las estructuras de Espada/Escudo (jefes, tiendas, precios, objetos del suelo) se basan en [PokeFeur Randomizer SWSH](https://github.com/JonatanUHC/PokeFeurRandomSWSH) (GPLv3) y pkNX. Las posiciones de los objetos regalados proceden de KM-Editor (GPLv3) y se verifican contra tu romfs antes de escribir. Nombres de especies en español: paquete `pokemon` de Sindre Sorhus (MIT).
