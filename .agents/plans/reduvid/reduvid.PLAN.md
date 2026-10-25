# Reduvid: hoja de ruta

Estado: `[x]` hecho · `[ ]` pendiente · `[~]` en curso. El ejecutor marca cada paso al terminarlo. Ante un imprevisto de diseño, **para** y anótalo en «Dudas abiertas»; no improvises. Convenciones y decisiones generales: `CLAUDE.md`.

## Decisiones de producto (motor)

- **Destinos** (`core/profiles.py`, datos y no código especial):
  - `jellyfin`: H.264 que se reproduce directo (sin transcodificar) en casi todo; es el destino por defecto, también para «no lo sé».
  - `modern`: H.265, más ahorro.
  - `archive`: H.265 con más compresión y preset más lento.
- **Perfil `jellyfin`:**
  - Vídeo: libx264, `-profile:v high`, `-level:v 4.1`, `-pix_fmt yuv420p` (8 bits). High@4.1 es lo que decodifica por hardware casi cualquier tele, móvil o navegador; con 10 bits o niveles superiores, Jellyfin transcodifica.
  - Resolución: el 4K se reduce a 1080p **por defecto**, con aviso, porque el nivel 4.1 no admite más de 1080p.
  - Contenedor: MKV por defecto (opción MP4).
  - Audio: AAC, AC3 y E-AC3 se copian. El resto (DTS, TrueHD, FLAC, Opus…) se convierte a AC3 a 640k si tiene más de 2 canales, o a AAC a 192k si es estéreo o mono.
  - Subtítulos de texto: se conservan (mov_text en MP4).
  - Subtítulos de imagen (PGS/VobSub): se conservan en MKV, avisando de que Jellyfin los «quemará»; en MP4 se descartan, avisando.
- **HDR/Dolby Vision** (`color_transfer` igual a `smpte2084` o `arib-std-b67`, o datos laterales DOVI): en `jellyfin`, conversión a SDR con `zscale` + `tonemap` si el FFmpeg instalado tiene los filtros; si no, aviso bloqueante y el usuario decide. En `modern`/`archive` se mantiene a 10 bits con H.265.
- **Calidad** (CRF; un número menor es mejor calidad):

  | Nivel | x264 | x265 |
  |---|---|---|
  | casi idéntica | 19 | 21 |
  | equilibrada (por defecto) | 22 | 24 |
  | máximo ahorro | 25 | 27 |

  Preset `medium`; en `archive`, `slow`.
- **Salida:** `<nombre>_reduvid.<ext>` en la carpeta del original o en la elegida. Si existe, `_reduvid (2)`, `(3)`… El temporal es `.<nombre>.reduvid-tmp.<ext>` en la carpeta destino y se escribe con `-f` explícito. Se renombra sin sobrescribir solo si la verificación pasa: la duración debe diferir ≤ max(1 s, 0,5 %) y el archivo debe abrir con ffprobe. Si la salida pesa ≥ el original, se descarta y se explica.
- **Proceso:**
  - FFmpeg con `-nostdin -hide_banner -progress pipe:1 -nostats`.
  - Prioridad baja con psutil (nice 10 en Linux, `BELOW_NORMAL_PRIORITY_CLASS` en Windows).
  - Pausa con `psutil.Process.suspend/resume`.
  - Cancelación: terminate → kill a los 5 s → se borra el temporal.
  - `-threads N` opcional.
- **Reemplazar el original:** desactivado por defecto; solo tras una verificación correcta y a la papelera (Send2Trash).

## Fase 0: preparación (0.0.1)

- [x] 0.1 Licencia WNCL-CU-1.0, rama `main`, remoto SSH, `CLAUDE.md` y este plan. *(sesión)*
- [x] 0.2 Andamiaje: `pyproject.toml` (hatchling, versión dinámica, extras `dev`, script `reduvid`), `src/reduvid/{__init__,__main__,cli}.py` con `--version` (solo eso), `tests/test_version.py`, configuración de ruff/mypy/pytest, `.pre-commit-config.yaml`, `scripts/check_doc_sync.py` + test, `.github/workflows/ci.yml` (ubuntu y windows; py 3.11 y 3.13; ruff, mypy, pytest, check_doc_sync). *Ejecutor: AgentRelay, esfuerzo medio.* Terminado cuando `pip install -e ".[dev]"`, `reduvid --version`, `pytest`, `ruff check .` y `mypy` pasan en local.
- [x] 0.3 Documentación base bilingüe: README, CHANGELOG, TODO, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, AUTHORS, THIRD_PARTY_NOTICES, `docs/{es,en}/README.md` y plantillas de `.github`. Versión 0.0.1. *(sesión)*
- [x] 0.4 Maquetas de las 3 direcciones de diseño en `docs/design/mockups.html`, publicadas como artifact (https://claude.ai/artifact/19SAanEVfYTEdjq8XbkAxw, privado). **Decisión del usuario:** las tres se incluyen como temas intercambiables; **Plegat** es el tema por defecto. Riso y Cinta se implementan como alternativas en el selector de tema (fase 2). Las propuestas iniciales A/B/C se descartaron por parecerse a estilos típicos de IA y se rehicieron como Riso, Cinta y Plegat. *(sesión, Opus)*
- [x] 0.5 FFmpeg instalado en este equipo con winget (`Gyan.FFmpeg` 9.0.2, incluye `libx264`, `libx265`, `libsvtav1`, `zscale`, `tonemap`, y aceleración NVENC/QSV/VAAPI/AMF). Los enlaces de winget quedan en el PATH de usuario; solo hace falta una terminal abierta después de instalarlo. *(sesión)*

## Fase 1: motor y CLI (0.1.0)

Rama `feat/motor` (pedir OK para crearla). Ejecutor por defecto: AgentRelay, esfuerzo medio; revisión de Opus/Sonnet. Cada paso, con sus tests y sin Qt.

- [x] 1.1 `core/ffmpeg.py` + tests. *(AgentRelay, esfuerzo medio; revisado)*
  - Localiza ffmpeg/ffprobe: ruta configurada, luego `shutil.which`.
  - Devuelve `FFmpegInfo`: versión, encoders `libx264`/`libx265`, filtros `zscale`/`tonemap` y encoders de hardware detectados (solo para informar).
  - Tests con salidas de `-encoders`/`-filters` simuladas.
- [x] 1.2 `core/probe.py` + tests: `ffprobe -v error -print_format json -show_format -show_streams -show_chapters` → dataclasses `MediaInfo`, `VideoStream` (códec, tamaño, fps, profundidad de bits, HDR/DV), `AudioStream` (códec, canales, idioma, por defecto), `SubtitleStream` (códec, idioma, imagen/texto, por defecto/forzado) y capítulos. Fixtures JSON en `tests/data/`. *(AgentRelay, esfuerzo medio; revisado)*
- [x] 1.3 `core/profiles.py` + `core/plan.py` + tests: `build_plan(media, options) -> EncodePlan`, una función pura que decide cada pista (copiar/recodificar/descartar), filtros y avisos tipados (`Warning(code, params)`, nunca texto). Aplica las reglas de arriba. *(AgentRelay, esfuerzo alto; revisado, corregido formato con `ruff format`)*
- [x] 1.4 `core/command.py` + tests: `EncodePlan` → `list[str]`. Conserva `-map_chapters`, `-map_metadata`, disposiciones y orden de pistas, y adjuntos/portada en MKV. Tests de rutas con espacios, tildes, emojis y nombres que empiezan por `-`. *(AgentRelay, esfuerzo alto; revisado. Adjuntos/portada en MKV completados en un paso posterior: ver «Decisiones resueltas»)*
- [x] 1.5 `core/naming.py` + `core/verify.py` + tests: nombre único, finalización sin sobrescribir (en POSIX `os.link` + `unlink`; en Windows `os.rename` falla si existe), verificación de duración y regla de «pesa más». *(AgentRelay, esfuerzo alto; revisado)*
- [x] 1.6 `core/runner.py` + tests: ejecución con progreso (`out_time_us`), velocidad, tiempo restante, pausa, cancelación sin huérfanos y prioridad baja. Errores de FFmpeg → `EncodeError(code, detail)` con códigos traducibles (sin espacio, archivo dañado, códec ausente, permiso denegado, desconocido). *(AgentRelay, esfuerzo xhigh; revisado. El ejecutor dejó archivos de validación fuera del código en el árbol de trabajo (caché pip, `runner-validation-*`, `encoded.mkv`); se limpiaron antes de aceptar)*
- [x] 1.7 `core/queue.py` + `core/report.py` + tests: cola secuencial, carpeta (recursiva opcional, filtro por extensión), progreso total ponderado por duración, eventos para la interfaz e informe de ahorro, errores y avisos. *(AgentRelay, esfuerzo alto; revisado, 1 reintento del propio ejecutor)*
- [x] 1.8 `cli.py`:
  - Órdenes `reduvid probe <archivos>` (resumen legible) y `reduvid convert <archivos|carpeta> --target --quality --container --max-height --output-dir --recursive --threads --replace-original --dry-run`.
  - Códigos de salida documentados.
  - Configuración en `platformdirs.user_config_dir("reduvid")` (TOML de lectura con `tomllib` y escritura propia mínima).
  - *(AgentRelay, esfuerzo xhigh; revisado. `--max-height` implementado de verdad en un paso posterior: ver duda resuelta)*
- [x] 1.9 Tests de integración (marcador `ffmpeg`): `tests/conftest.py` genera vídeos con lavfi (testsrc2 + 2 audios sine con idioma + srt + capítulos por ffmetadata; una variante de 10 bits) y prueba convertir, verificar, no sobrescribir y cancelar sin huérfanos. CI instala FFmpeg (apt; en Windows con `choco install ffmpeg` o una acción equivalente). *(AgentRelay, esfuerzo xhigh; revisado y validado con FFmpeg real (winget, fuera del PATH de la sesión: se usó la ruta absoluta de instalación). El ejecutor no tenía FFmpeg en su sandbox y escaló; se forzó la aceptación tras comprobar personalmente que los 4 tests pasan de verdad)*
- [x] 1.10 Docs y versión 0.1.0: uso de la CLI en README/README.en y `docs/{es,en}/cli.md`, y CHANGELOG. *(sesión, Opus; validado con FFmpeg real y pre-commit)*

## Fase 2: interfaz y asistente (0.2.0)

En `main`, sin rama (decisión del usuario, 24-10-2026). Cada paso añade su entrada en `## [Sin publicar]` de `CHANGELOG.md` y `CHANGELOG.en.md`; la versión sube a 0.2.0 solo en el 2.13, como se hizo con la 0.1.0. Maquetas de referencia: `docs/design/mockups.html` (pásala en `references` a los pasos de interfaz).

### Decisiones de la Fase 2

- **Arranque** (usuario): Reduvid es una aplicación gráfica. `reduvid` abre la interfaz (`[project.gui-scripts]`, sin consola en Windows) y `python -m reduvid` también. La CLI pasa a ser `reduvid-cli` (`[project.scripts]`), pensada para servidores Linux. Instalar sin Qt en servidores es cosa de la Fase 4 (anotado en `TODO.md`).
- **Qué conservar** (usuario): se elige **por idioma para toda la cola**, no pista a pista. `PlanOptions` gana `audio_languages: frozenset[str] | None = None` y `subtitle_languages: frozenset[str] | None = None` (`None` = todo). El idioma ausente se trata como `"und"`. Si en un vídeo el filtro no deja ningún audio, se conservan todos y se avisa con `Warning("audio_filter_kept_all")`. Los subtítulos sí pueden quedar en cero.
- **Fuentes** (usuario): se incluyen las seis familias OFL en `src/reduvid/resources/fonts/<familia>/` con su `OFL.txt`.
- **Textos**: los `msgid` van en inglés y hay catálogos `ca` y `es`; `en` usa el `msgid` tal cual. Los `.mo` no se suben (ya están en `.gitignore`): los compila un hook de hatch al construir o instalar (también en `pip install -e`), con Babel como dependencia del hook.
- **Idioma de la interfaz**: el de la configuración; si no hay, el del sistema (`LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG` y `locale.getlocale()`); si no es ca/es/en, inglés.
- **Modo de color**: Sistema (por defecto, `QStyleHints.colorScheme()`), Claro u Oscuro. Hay una preferencia «Reducir animaciones», porque Qt no lee la del sistema.
- **Paso «Calidad» sin tamaños**: los tamaños de la maqueta salen de la muestra de 30 s, que es de la Fase 3. En la 0.2.0 las tarjetas no muestran tamaño.
- **HDR sin `tonemap`** (aviso bloqueante): en el Resumen, un diálogo por vídeo con «Saltar este vídeo» (por defecto) o «Convertir igualmente (los colores se verán apagados)». Los vídeos saltados no entran en la cola. La CLI no cambia.
- **Semáforo Jellyfin**: se calcula en el motor (`core/compat.py`), no en la interfaz. Verde: se reproduce directo. Ámbar: algo hará que Jellyfin convierta (subtítulos de imagen que quemará, HDR o 10 bits conservados, perfil `modern`/`archive`). Rojo: hay un aviso bloqueante.
- **Tests de interfaz**: sin `pytest-qt` (no se añaden dependencias). Se usa `QT_QPA_PLATFORM=offscreen` y una `QApplication` de sesión en `tests/gui/conftest.py`. Si el CI de Ubuntu falla por librerías de Qt, se añaden con apt en `ci.yml` (`libegl1`, `libxkbcommon0`, `libfontconfig1`; compruébalo antes).
- **mypy**: estricto en todo `src/reduvid`. Si los tipos de PySide6 lo impiden, se permite un override solo para `reduvid.gui.*`, con un comentario que explique el motivo.

### Pasos

- [x] 2.1 **Motor: configuración, procesado compartido y errores con código.** *AgentRelay, esfuerzo alto.* Versión: entrada «Añadido/Cambiado» en Sin publicar.
  - `core/config.py`:
    - `Config` (dataclass inmutable) con: `ffmpeg_path: Path | None`, `language: Literal["ca","es","en"] | None`, `theme: Literal["plegat","riso","cinta"] = "plegat"`, `color_mode: Literal["system","light","dark"] = "system"`, `ui_mode: Literal["wizard","advanced"] = "wizard"`, `reduce_motion: bool = False`, `output_dir: Path | None` y los valores por defecto de destino, calidad y contenedor.
    - `config_path()` usa la misma llamada que hoy usa `cli.py` (`user_config_dir("reduvid")`).
    - `load_config(path=None) -> tuple[Config, tuple[str, ...]]`: la tupla lista las claves inválidas. Ignora las claves desconocidas y sigue aceptando `ffmpeg_path` en la raíz y `[ffmpeg] path`.
    - `save_config(config, path=None)`: escritor TOML mínimo propio (cadenas escapadas, booleanos, rutas como cadena). Escritura atómica a un temporal y luego `os.replace`; sobrescribir la configuración sí está permitido.
  - `core/pipeline.py`: lleva aquí el cierre `process` de `cli.py` como clase `FileProcessor` con `__call__`, `pause()`, `resume()` y `cancel()`; `cancel()` cancela el `EncodeHandle` en curso. Los `RuntimeError` actuales pasan a `PipelineError(code, detail)` con los códigos `cancelled` y `verification_failed`; este lleva el motivo de la verificación en `detail`.
  - `core/queue.py`:
    - `cancel()` además llama a `processor.cancel()` si existe.
    - `FileReport` gana `error_code: str | None`, que toma el `code` de `EncodeError`/`PipelineError`, `probe_failed` si falla ffprobe o `unknown`. `reason` sigue llevando el detalle técnico.
  - `cli.py` usa `core.config` y `core.pipeline` sin cambiar su comportamiento ni su salida.
  - Tests: ida y vuelta de configuración (rutas con espacios, tildes y comillas), claves inválidas, cancelación que llega al handle (con fakes) y `error_code` en los informes. Los tests existentes siguen en verde.
- [x] 2.2 **Traducción con gettext (motor y CLI).** *AgentRelay, esfuerzo alto.*
  - `reduvid/i18n.py`, sin Qt: `setup_language(lang: str | None) -> str` (devuelve el idioma efectivo, según la regla de arriba), `_()` y `ngettext()`; el dominio es `reduvid` y la carpeta `src/reduvid/locale/<lang>/LC_MESSAGES/`.
  - `reduvid/messages.py`, sin Qt: `warning_text(Warning) -> str` y `error_text(code) -> str`, con una frase clara sin jerga para cada código. Cubre todos los `Warning(...)` de `core/plan.py`, todos los `EncodeErrorCode`, `PipelineError` y `probe_failed`, y `audio_filter_kept_all` del paso 2.3.
  - Hook de hatch (`hatch_build.py`, con `[tool.hatch.build.hooks.custom]` y `dependencies = ["babel"]`): compila los `.po` a `.mo` y los incluye como `artifacts`.
  - `scripts/compile_translations.py`, para desarrollo, y la configuración de extracción de Babel (`babel.cfg`, o `[tool.babel]` si lo admite; compruébalo).
  - `src/reduvid/locale/reduvid.pot`, con `ca` y `es` traducidos para todo lo que exista hasta aquí.
  - `cli.py`: todos los textos pasan por `_()` y la orden acepta `--lang`.
  - Tests: cada código de `messages` tiene texto en ca y es (no vacío y distinto del `msgid`); un test comprueba que el `.pot` está al día (re-extracción y comparación de `msgid`, sin fechas).
  - Docs: `CONTRIBUTING(.en).md`, cómo actualizar las traducciones.
- [x] 2.3 **Motor: filtro por idioma y semáforo Jellyfin.** *AgentRelay, esfuerzo alto.*
  - `PlanOptions.audio_languages`/`subtitle_languages`, con la regla de arriba, en `core/plan.py`.
  - `core/compat.py`: `jellyfin_status(plan) -> CompatStatus(level: Literal["direct","partial","blocked"], reasons: tuple[Warning, ...])`.
  - CLI: `--keep-audio ca,es` y `--keep-subs ca,und`, documentados en `docs/{es,en}/cli.md`.
  - Tests de plan con varios idiomas, `und`, el caso de cero audios y los tres niveles del semáforo.
- [x] 2.4 **Tipografías.** *Sesión (Sonnet, esfuerzo medio), con la Skill `licencias` obligatoria.*
  - Se descargan del repositorio oficial `google/fonts` (`ofl/<familia>/`) las seis familias: Bricolage Grotesque, Instrument Sans, Archivo, Atkinson Hyperlegible, Barlow + Barlow Condensed y JetBrains Mono. Se prefieren las variables; se comprueban la ruta y el nombre exactos al descargar, sin suponerlos.
  - Cada familia lleva su `OFL.txt` en `src/reduvid/resources/fonts/<familia>/` y se incluye en el wheel.
  - Se actualizan `THIRD_PARTY_NOTICES.md` (las dos secciones), el `REUSE.toml` si existe y la frase «El repositorio no incluye material de terceros».
  - Terminado cuando `python -c` carga cada archivo con `QFontDatabase.addApplicationFont` sin devolver -1.
- [x] 2.5 **Temas: tokens → QSS.** *AgentRelay, esfuerzo alto; con `docs/design/mockups.html` en references.*
  - `gui/theme/tokens.py`, Python puro: `ThemeTokens` (bg, surface, text, muted, line, accent, accent2, accent3?, fold?, on_accent, soft, warn_bg, warn_fg, track, radius, bordes, familias display/body/mono y pesos). Valores **exactos** de la maqueta para plegat/riso/cinta en claro y oscuro: `THEMES[(name, mode)]`.
  - `gui/theme/qss.py`: `build_qss(tokens) -> str`. QSS no tiene variables: se sustituyen los valores. Los degradados se escriben con `qlineargradient` y los selectores usan `objectName` y propiedades dinámicas (`[role="primary"]`, `[checked="true"]`…). Lo que QSS no sabe hacer (sombra desplazada de Riso, esquina doblada de Plegat, tramado) queda para el 2.11.
  - `gui/theme/fonts.py`: registra las fuentes del 2.4 una sola vez y devuelve las familias reales.
  - `gui/theme/manager.py`: aplica un tema y un modo a la `QApplication` y reacciona al cambio de esquema del sistema.
  - Tests:
    - Contraste WCAG ≥ 4,5 en text/bg, text/surface, muted/bg y on_accent/accent, en los seis juegos. **Si alguno no pasa, para y anótalo en Dudas: no cambies colores**, que es una decisión de diseño.
    - `build_qss` no deja ningún `{` sin sustituir.
- [x] 2.6 **Esqueleto de la aplicación.** *AgentRelay, esfuerzo xhigh; maquetas en references.*
  - `gui/app.py` (`main()`) y entradas de `pyproject`: `reduvid` (gui-script) y `reduvid-cli`. `__main__.py` abre la interfaz.
  - Se actualizan README(.en), `docs/{es,en}/cli.md` y los ejemplos con `reduvid-cli`.
  - `gui/main_window.py`, con la estructura de la maqueta:
    - Barra superior: marca y conmutador Asistente/Avanzado.
    - Debajo, tres columnas: lista de pasos (180 px), contenido y cola (300 px).
    - Con poca anchura, se apilan como en la maqueta.
  - `gui/preferences.py`: tema, modo de color, idioma (se aplica al reiniciar y la interfaz lo avisa), reducir animaciones y ruta de FFmpeg con «Examinar» y «Comprobar». Todo se guarda con `core.config`.
  - `gui/ffmpeg_missing.py`: pantalla clara cuando no hay FFmpeg, con cómo instalarlo en Windows (`winget install Gyan.FFmpeg`) y en Linux (apt/dnf), y botones «Elegir ffmpeg…» y «Volver a buscar».
  - Tests offscreen: la ventana se crea con cada tema y modo, y la pantalla de FFmpeg ausente aparece si `detect_ffmpeg` devuelve `None`.
- [x] 2.7 **Trabajo en segundo plano y panel de cola.** *AgentRelay, esfuerzo xhigh.*
  - `gui/workers.py`:
    - `ProbeWorker` sondea los vídeos al añadirlos.
    - `QueueWorker` ejecuta `ConversionQueue` + `core.pipeline.FileProcessor` en un `QThread`.
    - Los callbacks del motor llegan a la interfaz solo como señales; nunca se toca un widget desde otro hilo.
  - `gui/queue_panel.py`:
    - Vídeo actual con tamaño, porcentaje y tiempo restante, barra, y botones Pausar/Reanudar y Cancelar.
    - Lista con fichas de aviso por vídeo (texto de `messages.warning_text`) y total estimado.
    - Mensajes de estado como los de la maqueta («En pausa…», «Cancelado. No queda ningún archivo a medias.», «Listo y verificado…»).
  - `gui/error_view.py`: muestra el error traducido con `error_text(error_code)` y un desplegable «Ver detalles técnicos» con `reason`, que se puede copiar.
  - Al cerrar con una conversión en marcha, se pregunta y se cancela limpiamente.
  - Tests offscreen con un `FileProcessor` falso: progreso, pausa, cancelación y error.
- [x] 2.8 **Asistente, pasos 1-3 y componentes.** *AgentRelay, esfuerzo alto; maquetas en references.*
  - Componentes en `gui/widgets/`:
    - `OptionCard`: tarjeta seleccionable con nombre, etiqueta y descripción; accesible como botón de opción.
    - `WhatIsThis`: desplegable «¿Qué es esto?».
    - `StepList`: hecho / actual / pendiente.
    - `WizardNav`: Atrás / Siguiente: <paso>.
  - Paso 1, Vídeos: añadir archivos o carpeta (con casilla «incluir subcarpetas»), arrastrar y soltar, quitar, y estado del sondeo.
  - Paso 2, ¿Dónde los vas a ver?: Jellyfin (tele, móvil, navegador), Aparatos modernos (`modern`), Guardar para archivo (`archive`) y «No lo sé», que usa `jellyfin`. Cada opción lleva su explicación.
  - Paso 3, Calidad: las tres tarjetas con los textos de la maqueta, la recomendación según el destino y «¿Qué es esto?» con la explicación del CRF.
  - Tests offscreen: navegación, y el botón Siguiente desactivado sin vídeos.
- [x] 2.9 **Asistente, pasos 4-6 y arranque.** *AgentRelay, esfuerzo alto.*
  - Paso 4, Qué conservar: casillas de idiomas de audio y de subtítulos encontrados en la cola, con su nombre legible; `und` se muestra como «Sin idioma indicado». Por defecto, todo marcado.
  - Paso 5, Destino:
    - Misma carpeta u otra, y MKV/MP4 con explicación.
    - «Reemplazar el original» desactivado por defecto y explicado («va a la papelera solo si la copia se verifica»).
    - Opción de reducir a 1080p si hay 4K y el destino es jellyfin.
  - Paso 6, Resumen: lista por vídeo con el semáforo de `compat.jellyfin_status`, los avisos traducidos, el diálogo de HDR bloqueante (ver decisiones) y el botón «Empezar», que lanza el `QueueWorker` y muestra el informe final (ahorro total, errores con detalle).
  - Tests offscreen del cálculo de idiomas, del diálogo bloqueante y de la construcción de `PlanOptions`.
- [x] 2.10 **Modo Avanzado.** *AgentRelay, esfuerzo alto.*
  - Una sola página con todas las opciones de la CLI (destino, calidad, contenedor, altura máxima, carpeta de salida, subcarpetas, hilos, reemplazar original e idiomas) y la misma cola y el mismo resumen con semáforo.
  - El cambio de modo conserva la selección y el modo elegido se guarda en `ui_mode`.
- [x] 2.11 **Motivos pintados de cada tema.** *AgentRelay, esfuerzo xhigh; revisión visual de Opus con capturas.* En `gui/widgets/motifs.py` y `gui/widgets/progress.py`: *(revisado con capturas reales de la ventana y renderizado aislado de los 6 juegos de tema; corregido el solape del texto de porcentaje con el gato en Riso, alineándolo a la derecha. Sombra de Riso en botones primarios queda pendiente: todavía no hay ningún botón con role=primary en el proyecto)*
  - **Plegat**: esquina doblada en la tarjeta elegida, barra en acordeón y gato de origami que se pliega con el progreso.
  - **Riso**: sombra desplazada en tarjetas y botones, pista tramada, gato que se acurruca y cifra que se estrecha con `QFont.setVariableAxis("wdth")` (si no funciona, cifra fija).
  - **Cinta**: franja de tres colores, bobinas que se vacían y se llenan, y contador mecánico de MB ahorrados.
  - Con «Reducir animaciones» se salta directamente al estado final.
  - Todo se pinta desde los tokens, sin colores fijos en el código.
- [x] 2.12 **Accesibilidad y traducciones completas.** *AgentRelay, esfuerzo alto; la sesión revisa los textos en catalán y castellano.* *(Revisión visual en casa completada. Hallazgos corregidos: el anillo de foco no se pintaba en `QComboBox` y controles similares con el estilo nativo de Windows — se fuerza `QApplication.setStyle("Fusion")` en `ThemeManager`, que respeta el QSS completo; atajos Alt confirmados funcionando (p. ej. Alt+A activa «Asistente»); a 200% la ventana nacía más ancha que la pantalla y la cola quedaba cortada — el tamaño inicial ahora se acota a `screen().availableSize()`, dejando que el apilado vertical ya existente haga el resto; probado también a 150%. Catalán: 0 mensajes sin traducir de 242, calidad alta; corregidos 2 castellanismos («guardar»/«Guardar» → «desar»/«Desa») para ser consistentes con el resto del catálogo.)*
  - Orden de tabulación lógico, atajos (`Alt+` en botones), foco visible en el QSS de los tres temas, y `accessibleName`/`accessibleDescription` en los controles personalizados.
  - Nada se corta con escalado de 150 % y 200 % (`QT_SCALE_FACTOR`).
  - Re-extraer el `.pot` y completar `ca` y `es`.
  - Test que recorre la ventana y falla si un control interactivo no tiene nombre accesible.
- [x] 2.13 **Capturas, documentación y 0.2.0.** *Sesión (Opus).* *(El modo offscreen de Qt en este equipo no tiene fuentes registradas, así que `scripts/screenshots.py` offscreen habría dado capturas con texto vacío; en su lugar se generaron con la ventana real, lanzada con datos de ejemplo mediante un script de desarrollo descartable, para los 3 temas × claro/oscuro. No se creó `scripts/screenshots.py`: si se quiere automatizar en un equipo con fuentes offscreen correctas, queda pendiente)*
  - `scripts/screenshots.py`: genera con offscreen y datos de ejemplo las capturas de los tres temas en claro y oscuro en `docs/screenshots/`.
  - README(.en): capturas, cómo abrir la interfaz y enlace a `docs/{es,en}/gui.md` (uso del asistente y del modo Avanzado).
  - Versión 0.2.0 en `__init__.py` y CHANGELOG(.en): se pasa Sin publicar a `[0.2.0]`. Es menor: añade la interfaz, y el cambio de `reduvid` a `reduvid-cli` antes de 1.0.0 cuenta como menor.
  - Se quitan las tareas hechas de TODO(.en).
  - Terminado cuando pasan `pytest`, `ruff`, `mypy`, `pre-commit` y `check_doc_sync`, y la aplicación se abre y convierte un vídeo de prueba de verdad.

## Fase 3: ayudas (0.3.0)

Muestra de 30 s (en el 40 % del vídeo) con estimación y comparación de fotograma antes/después, estimación de tamaño y tiempo, informe final, perfiles guardados y avisos de HDR, 10 bits y subtítulos de imagen en la interfaz. Objetivo del usuario: 24-10-2026, «hacerlo todo» hasta tener algo instalable y probarlo con un Windows (instalador) y un Debian (reducir un vídeo real de 6 GB).

### Decisiones de la Fase 3

- **Muestra de 30 s:** se recorta con FFmpeg (`-ss <40%> -t 30`) a un archivo temporal en el directorio de caché del usuario (`platformdirs.user_cache_dir("reduvid")`), se codifica con el plan ya calculado y se borra al cerrar la aplicación o al descartar la muestra. Nunca se guarda junto al original.
- **Comparación de fotograma antes/después:** un fotograma a mitad de la muestra (no del vídeo completo, para no tardar), extraído con ffprobe/ffmpeg a PNG temporal, mostrado lado a lado (o con deslizador si acaba siendo sencillo en QSS/Qt; si resulta complejo, lado a lado y se anota en el plan).
- **Estimación de tamaño y tiempo:** tamaño, igual que ahora hace la muestra (ya extrapolable: tamaño_muestra / 30 s × duración_total). Tiempo: se mide la velocidad real de codificación de la muestra (x tiempo real) y se extrapola a la duración total; si no hay muestra calculada, se oculta el dato en vez de inventar un número.
- **Perfiles guardados:** un perfil es un `PlanOptions` con nombre, guardado en `platformdirs.user_config_dir("reduvid")/profiles/<nombre>.toml` (mismo escritor TOML atómico que `core/config.py`). La interfaz permite guardar la combinación actual del asistente/Avanzado con un nombre y cargarla después; no hay perfiles de fábrica más allá de jellyfin/modern/archive, que ya existen como destino.
- **Avisos de HDR/10 bits/subtítulos de imagen:** ya calculados por el motor (`core/plan.py`, `core/compat.py`); esta fase solo añade su aparición también en el paso de Calidad/Resumen antes de la muestra, para que el usuario los vea antes de gastar tiempo en una muestra o conversión completa.

### Pasos

- [x] 3.1 **Motor: recorte de muestra y estimación.** *(AgentRelay, esfuerzo alto; revisado, 288/292 tests en verde, 4 de integración saltados por no detectar FFmpeg en el PATH de esta sesión de Bash)* *AgentRelay, esfuerzo alto.* Versión: entrada en Sin publicar.
  - `core/sample.py`: `build_sample_command(path, plan, start, duration) -> list[str]` (recorte + codificación con el plan ya calculado, usando `-ss`/`-t` antes de `-i` para que sea rápido) y `extract_frame_command(path, timestamp) -> list[str]` (un PNG a un temporal).
  - `core/estimate.py`: `estimate_from_sample(original_sample_bytes, encoded_sample_bytes, sample_duration, total_duration, elapsed_encode_seconds) -> Estimate` (dataclass con `estimated_total_bytes`, `estimated_total_seconds`), pura, sin I/O.
  - Tests: comandos generados (rutas con espacios/tildes, `-ss` antes de `-i`), y la extrapolación aritmética con casos límite (muestra más corta que 30 s si el vídeo dura menos de 75 s, duración cero).
- [x] 3.2 **Motor: perfiles guardados.** *(AgentRelay, esfuerzo medio; revisado, 302/306 tests en verde)*
  - `core/profile_store.py`: `list_profiles()`, `load_profile(name)`, `save_profile(name, options)`, `delete_profile(name)`, mismo escritor TOML atómico que `core/config.py` (puede reusar su función interna si ya está extraída, o duplicarla mínimamente si no merece la pena abstraer).
  - Tests: ida y vuelta de un `PlanOptions` completo (incluye `audio_languages`/`subtitle_languages` como `frozenset`), nombres con espacios/tildes, perfil inexistente.
- [x] 3.3 **Interfaz: muestra y comparación en el paso Calidad.** *(AgentRelay, esfuerzo xhigh; revisado con auditoría de diseño aparte sobre hilos/temporales/invalidación, sin bloqueantes; 308/312 tests en verde)*
  - Botón «Probar con una muestra de 30 s» en el paso 3 (Calidad), que lanza `QueueWorker`-like en segundo plano (reusar el patrón de hilos de `gui/workers.py`, nunca tocar widgets desde otro hilo).
  - Panel de resultado: dos imágenes (antes/después) con `QLabel`+`QPixmap`, tamaño estimado y porcentaje de ahorro, con los tokens de tema (tarjeta `#card`, colores habituales).
  - Si cambia la calidad elegida, la muestra anterior se invalida y hay que volver a pedirla (no se recalcula sola).
  - Tests offscreen: arranque de la muestra, resultado mostrado, invalidación al cambiar de calidad.
- [x] 3.4 **Interfaz: estimación de tamaño/tiempo sin muestra.** *(AgentRelay, esfuerzo medio; revisado, 311/315 tests en verde. Nota: `estimate_from_sample` tiene el parámetro `original_sample_bytes` sin usar desde el 3.1, se arrastra sin afectar al resultado; limpiar en una pasada de pulido si se retoma `core/estimate.py`)*
  - Si no hay muestra calculada, el paso Resumen no muestra tamaño/tiempo estimado (como ahora); si la hay, los usa para todos los vídeos de la cola con las mismas opciones (extrapolando por duración de cada uno).
  - Tests: con y sin muestra.
- [x] 3.5 **Interfaz: perfiles guardados.** *(AgentRelay, esfuerzo alto; revisado, 316/320 tests en verde. Decisión de la sesión: va en el paso Calidad, no en Preferencias, por ser el paso central de decisión del asistente)*
  - En el paso Calidad, desplegable para cargar un perfil y botón «Guardar como perfil…» con diálogo de nombre.
  - Aplicar un perfil rellena todo el estado del asistente (destino, calidad, contenedor, idiomas, etc.), igual que si el usuario lo hubiera elegido paso a paso.
  - Tests offscreen: guardar, listar, cargar, eliminar.
- [x] 3.6 **Interfaz: avisos tempranos de HDR/10 bits/subtítulos de imagen.** *(AgentRelay, esfuerzo medio; revisado, 321/325 tests en verde)*
  - En el paso Calidad, mostrar los avisos relevantes del plan actual (ya calculados por el motor) antes de que el usuario llegue al Resumen, para que no se lleve la sorpresa solo al final.
  - Tests: aviso visible cuando aplica, ausente cuando no.
- [x] 3.7 **Docs y versión 0.3.0.** *(Sesión, Opus; verificado con FFmpeg real: 325/325 tests en verde incluida la suite de integración, y la muestra de 30 s probada de extremo a extremo contra un vídeo generado con FFmpeg, con recorte y los dos fotogramas de comparación generados de verdad)*
  - README(.en) y `docs/{es,en}/gui.md`: cómo usar la muestra, la comparación y los perfiles guardados.
  - Versión 0.3.0 en `__init__.py` y CHANGELOG(.en): Sin publicar → `[0.3.0]`. Menor: añade funcionalidad compatible.
  - Terminado cuando pasan `pytest`, `ruff`, `mypy`, `pre-commit`, `check_doc_sync`, y una muestra real de 30 s con FFmpeg de verdad se ve y se guarda/carga un perfil real.

## Fase 4: empaquetado y publicación (0.4.0 → 1.0.0)

Objetivo: instalador de Windows funcional (probado en un Windows real) y paquete instalable en Debian (probado reduciendo un vídeo real de 6 GB). Primera release pública solo con OK explícito del usuario.

### Decisiones de la Fase 4

- **Windows:** PyInstaller en modo `--onedir` (carpeta, no `--onefile`), porque la LGPL de PySide6 exige poder sustituir la biblioteca Qt sin recompilar la app; eso solo es practicable en modo carpeta. Instalador con Inno Setup (gratuito, script de texto versionable en el repo, sin dependencias de pago). Sin firma de código por ahora (certificado de pago; se anota en TODO si se quiere más adelante) — avisar al usuario de que Windows SmartScreen mostrará advertencia la primera vez.
- **Debian/Linux:** AppImage como formato principal (no exige instalación como root ni gestor de paquetes concreto). Evaluar `.deb` nativo más adelante si AppImage no basta para el test con Debian (anotado ya en TODO como prioridad baja); para el test de este plan, AppImage es suficiente si funciona.
- **FFmpeg nunca se empaqueta** (ya decidido en CLAUDE.md): el instalador de Windows debe comprobar si hay FFmpeg y, si no, mostrar la pantalla ya existente (`gui/ffmpeg_missing.py`) con instrucciones; no se añade descarga automática sin que el usuario lo pida explícitamente (sería una decisión nueva, preguntar si aparece la tentación).
- **PyPI/pipx:** se deja para después de probar los dos instaladores (Windows y Debian); no bloquea el test de este plan. Queda como paso 4.5, al final.
- **CI de artefactos:** generar los paquetes en GitHub Actions (ubuntu-latest y windows-latest, ya en `ci.yml`) para que sean reproducibles y no dependan solo del equipo de este usuario; los artefactos de prueba para el test local pueden generarse también a mano mientras tanto.

### Pasos

- [x] 4.0 **Icono de la aplicación.** *(Sesión, Opus; aprobado por el usuario)* `src/reduvid/resources/icon/reduvid.{ico,png,svg}`: el gato de origami de Plegat (reusando `draw_origami_cat` de `gui/widgets/motifs.py` para el trazado, sin redibujarlo a mano) sobre fondo teal (`accent` de Plegat claro), cabeza en `accent2`. El `.ico` lleva 7 resoluciones (16 a 256 px); el `.svg` reproduce las mismas coordenadas, verificado renderizándolo y comparando píxel a píxel con el PNG.
- [x] 4.1 **Windows: PyInstaller en modo carpeta.** *(AgentRelay, esfuerzo alto; revisado y verificado generando el paquete de verdad: `dist/windows/Reduvid/Reduvid.exe` arranca, fuentes y traducciones incluidas, 322/326 tests en verde)*
  - `packaging/windows/reduvid.spec` (PyInstaller): usa el icono del paso 4.0, `reduvid.__main__` como entrada, excluye módulos de desarrollo (pytest, mypy, ruff, babel, pre_commit) del bundle.
  - `scripts/build_windows.py` compila las traducciones y ejecuta PyInstaller, deja el resultado en `dist/windows/`.
- [x] 4.2 **Windows: instalador Inno Setup.** *(AgentRelay, esfuerzo alto; revisado y compilado de verdad con Inno Setup 6.7.3 instalado en el equipo de desarrollo: `Reduvid-Setup-0.3.0.exe` se genera sin avisos tras corregir `ArchitecturesAllowed`/`ArchitecturesInstallIn64BitMode` de `x64` a `x64compatible`, deprecado en esa versión. Falta la prueba de instalación en un Windows limpio aparte de este equipo de desarrollo, prevista en la prueba de aceptación de la Fase 4.)*
  - `packaging/windows/reduvid.iss`: instala la carpeta de PyInstaller en Archivos de Programa, crea acceso directo en el menú inicio (opcional en escritorio), desinstalador limpio, versión tomada de `__init__.py` (pasada como parámetro al compilar, no hardcodeada).
  - Documentado en `docs/{es,en}/instalacion.md`, enlazado desde ambos README.
- [x] 4.3 **Linux: AppImage.** *(AgentRelay, esfuerzo alto; revisado. Sintaxis bash validada con bash real vía WSL Debian; appimagetool 1.9.1 y el runtime de AppImage con versión fijada. Ni este equipo (Windows) ni el entorno del ejecutor tienen FUSE/herramientas de AppImage: la generación y ejecución real del `.AppImage` NO se ha probado todavía — queda para la prueba de aceptación de la Fase 4, en la Debian real del usuario.)*
  - `packaging/linux/` con el `AppDir` (`AppRun`, `.desktop`, icono) y script de construcción `build_appimage.sh` con `appimagetool`.
- [ ] 4.4 **CI de artefactos.** *AgentRelay, esfuerzo medio.*
  - `ci.yml`: job que construye el `.exe`/instalador en windows-latest y el `.AppImage` en ubuntu-latest, los sube como artefactos de la ejecución (no publica release todavía).
  - Terminado cuando un push a `main` deja descargables ambos artefactos desde la pestaña Actions.
- [ ] 4.5 **pipx/PyPI (si procede tras probar los instaladores).** *Pendiente de decidir alcance tras 4.1-4.4.*
- [ ] 4.6 **Revisión final de licencias, capturas actualizadas y primera release.** *Sesión (Opus); Skill `licencias` obligatoria.* Requiere OK explícito del usuario para crear el tag y publicar. Versión 1.0.0 (mayor: primera versión considerada estable/instalable por cualquiera, puede justificar el salto si hay algún cambio incompatible pendiente; si no hay ninguno, valorar si no sería más bien 0.4.0 y dejar 1.0.0 para más adelante — decidirlo en el momento con lo que haya cambiado realmente, no de antemano).

### Prueba de aceptación de la Fase 4 (con el usuario)

1. Instalar el `.exe` de Inno Setup en un Windows real (no este equipo de desarrollo) y comprobar que abre y funciona.
2. Instalar/ejecutar el `.AppImage` en un Debian real y usarlo para reducir un vídeo real de unos 6 GB de principio a fin (incluye verificación y, si aplica, reemplazo a papelera).
3. Cualquier fallo encontrado en este paso se trata como bloqueante antes de considerar la Fase 4 cerrada, incluso si ya se había marcado algún paso anterior como hecho.

## Decisiones resueltas (histórico)

- **Contribuciones externas de código:** se exigirá **DCO** (Developer Certificate of Origin), no un CLA. Quien contribuye certifica con `Signed-off-by` en el commit que el código es suyo y lo aporta bajo WNCL-CU-1.0; no hay cesión de derechos a Catlinux ni papeleo aparte. Es el mínimo habitual en proyectos pequeños de un solo mantenedor; un CLA sería desproporcionado aquí. Pendiente de aplicar en `CONTRIBUTING.md`/`.en.md` (quitar el bloqueo de PRs de código y explicar el DCO) cuando se abra el repositorio a contribuciones.
- **`--max-height` soportado de verdad:** `PlanOptions` gana el campo `max_height: int | None = None` (por defecto 1080, el límite del nivel 4.1 en jellyfin). `VideoDecision.reduce_to_1080p` (bool) se sustituyó por `target_height: int | None` para poder llevar cualquier altura objetivo, no solo 1080; `command.py` genera `scale=-2:<target_height>`. Solo afecta al perfil jellyfin, igual que antes. *(AgentRelay, esfuerzo alto; revisado y probado con la CLI real contra un vídeo generado con FFmpeg)*
- **Adjuntos y portada en MKV:** `probe.py` añade `AttachmentStream` (index, filename, mime_type) y `MediaInfo.attachments` (streams con `codec_type: attachment` en ffprobe, con valor por defecto `[]` para no romper construcciones posicionales existentes). `command.py` los copia con `-map 0:<index> -c:t copy` solo cuando `plan.container == "mkv"`; en MP4 se omiten sin aviso (detalle técnico de compatibilidad de contenedor). *(AgentRelay, esfuerzo alto; revisado, 70/70 tests en verde incluida la suite de integración con FFmpeg real)*

## Dudas abiertas

- **Reducción 4K desmarcada (2.9):** con `max_height=2160` el motor sigue emitiendo el aviso `resolution_reduced_4k_to_1080p` y `scale=-2:2160` (no-op), aunque el vídeo no se reduzca a 1080p. Decidir si el motor debe distinguir el caso (aviso y filtro) o se deja así.
