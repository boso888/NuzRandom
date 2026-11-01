# NuzRandom 0.3.1

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
| Salvajes | modo, coherencia (hueco / zona / todo el juego / una especie por zona), legendarios, visibles en el mapa, combate oculto, capturar salvajes de cualquier nivel, total de estadísticas mínimo y máximo, niveles ± %, objetos equipados |
| Starters y regalos | aleatorios / fuerza similar / elegidos por nombre, solo básicos, solo líneas de 3 fases, sin tipos repetidos, triángulo Planta-Fuego-Agua, legendarios; regalos, intercambios y encuentros fijos |
| Entrenadores | especies (aleatorio / similar / temático por tipo), legendarios, sin repetidos, evolución forzada desde un nivel, niveles ± %, movimientos según nivel, IA máxima, IV perfectos, naturalezas |
| Jefes | equipos de 6, primer combate contra el rival, modo propio, legendarios, total de estadísticas mínimo, evolución forzada, niveles extra, IA, IV, objetos de combate, añadir o quitar jefes por ID |
| Pokémon | tipos, habilidades (con o sin Superguarda), estadísticas (mezclar / redistribuir), coherencia evolutiva, ratio de captura mínimo, curva y cantidad de experiencia |
| Movimientos | por nivel (con primer ataque de daño y % del propio tipo), prohibir fulminantes, MT/DT y su compatibilidad, potencia, precisión, PP y tipo |
| Evoluciones | intercambio/amistad a nivel, métodos raros a nivel, nivel máximo o porcentaje, evoluciones aleatorias |
| Objetos y tiendas | % de precio, conservar objetos para vender, Repelente Máximo, Caramelos Raros y su precio, otros objetos para la tienda, tiendas secundarias y de MT, % de objetos de evolución, objetos del suelo, ocultos y regalados, MT en el mundo, lista de objetos prohibidos |
| General | semilla reproducible, generaciones permitidas, registro de cambios, guardar y cargar ajustes, diagnóstico |

## Combate oculto (Espada/Escudo 1.3.2)

Con esta opción, el Pokémon que ves por el mapa no es el que combates: al tocarlo, el combate es contra otra especie al azar. Así no puedes elegir qué capturar.

Los archivos del romfs no pueden hacerlo, porque el modelo y el combate salen del mismo dato. Lo hace el módulo del juego (ExLaunch) de [PokeFeur Randomizer SWSH](https://github.com/JonatanUHC/PokeFeurRandomSWSH), que NuzRandom **no incluye**:

1. Descarga PokeFeur Randomizer SWSH y deja su carpeta como `PokeFeurRandomSWSH`, junto a la de NuzRandom, o elígela en la pestaña **Salvajes**.
2. Activa **Lo que ves en el mapa no es lo que combates** y elige el modo: otro distinto en cada combate, igual en toda la zona o igual en todo el juego.
3. **Randomizar**. NuzRandom copia el módulo a la carpeta `exefs` del mod y su configuración a `sdcard/config/swsh-mods-exl/config.toml` del emulador. Si ya había una de otra herramienta, la guarda como `config.toml.antes_de_nuzrandom`.

Solo funciona con la actualización 1.3.2. El Pokémon del combate respeta los legendarios y los filtros de estadísticas de la pestaña Salvajes.

## Capturar salvajes de cualquier nivel (Espada/Escudo 1.3.2)

Espada y Escudo **no dejan capturar Pokémon salvajes de más nivel del que permiten tus medallas**. Al tirar la Poké Ball, el juego dice que contra ese rival no sirven las Poké Balls.

| Medallas | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| Nivel máximo para capturar | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 | sin límite |

Con los niveles de salvajes subidos (*Niveles salvajes ± %*), pasa a menudo, sobre todo en el Área Silvestre. Por ejemplo, con 3 medallas no puedes capturar un Lucario de nivel 36.

La opción **Capturar salvajes de cualquier nivel** (pestaña **Salvajes**) quita ese bloqueo. Usa el mismo módulo de PokeFeur que el combate oculto (ver arriba), pero funciona aunque el combate oculto esté apagado. Efecto secundario: en el Área Silvestre pueden aparecer Pokémon de nivel más alto.

### Arreglarlo en una partida ya empezada (sin volver a randomizar)

Volver a pulsar *Randomizar* cambia la semilla, así que no lo hagas a mitad de un nuzlocke. Basta con tocar la configuración del módulo. Cierra el juego antes de empezar.

**Si usas el combate oculto**, el módulo ya está instalado:

1. Abre el archivo de configuración del módulo:
   - Ryujinx: `%APPDATA%\Ryujinx\sdcard\config\swsh-mods-exl\config.toml`
   - Yuzu y derivados: `%APPDATA%\yuzu\sdmc\config\swsh-mods-exl\config.toml`
2. Busca la sección `[uncap_level]` y déjala así:
   ```toml
   [uncap_level]
   active = true
   fully = true
   ```
3. Guarda y abre el juego. No cambia nada más de tu partida.

**Si no usas el combate oculto**, primero hay que añadir el módulo al mod:

1. Descarga [PokeFeur Randomizer SWSH](https://github.com/JonatanUHC/PokeFeurRandomSWSH) y abre `assets\exlaunch\0100ABF008968000` (Espada) o `assets\exlaunch\01008DB008C2C000` (Escudo).
2. Copia `subsdk9_ryujinx` y `main.npdm_ryujinx` (en Yuzu, las versiones `_stable`) a la carpeta `exefs` de tu mod (créala si no existe) y quítales la terminación: deben llamarse `subsdk9` y `main.npdm`.
   - Ryujinx: `%APPDATA%\Ryujinx\mods\contents\<ID del juego>\NuzRandom\exefs\`
   - Yuzu: `%APPDATA%\yuzu\load\<ID del juego>\NuzRandom\exefs\`
3. Crea el `config.toml` en la ruta del paso 1 del caso anterior con solo esto:
   ```toml
   [uncap_level]
   active = true
   fully = true
   ```
4. Abre el juego. Solo funciona con la actualización 1.3.2.

Los cambios en `config.toml` se pierden si vuelves a pulsar *Randomizar*. Para tu próximo nuzlocke, marca la opción en la app.

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

GPLv3. Las estructuras de Espada/Escudo (jefes, tiendas, precios, objetos del suelo) se basan en [PokeFeur Randomizer SWSH](https://github.com/JonatanUHC/PokeFeurRandomSWSH) (GPLv3) y pkNX. Las posiciones de los objetos regalados proceden de KM-Editor (GPLv3) y se verifican contra tu romfs antes de escribir. El combate oculto usa el módulo ExLaunch de PokeFeur Randomizer SWSH (GPLv3), basado en [swsh-mods-exl](https://github.com/lincoln-lm/swsh-mods-exl) de Lincoln-LM. Nombres de especies en español: paquete `pokemon` de Sindre Sorhus (MIT).
