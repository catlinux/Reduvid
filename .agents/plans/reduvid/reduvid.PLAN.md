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
- [x] 1.4 `core/command.py` + tests: `EncodePlan` → `list[str]`. Conserva `-map_chapters`, `-map_metadata`, disposiciones y orden de pistas, y adjuntos/portada en MKV. Tests de rutas con espacios, tildes, emojis y nombres que empiezan por `-`. *(AgentRelay, esfuerzo alto; revisado. Adjuntos/portada en MKV pendientes: `MediaInfo` del paso 1.2 no expone streams de adjuntos todavía; retomar si hace falta)*
- [x] 1.5 `core/naming.py` + `core/verify.py` + tests: nombre único, finalización sin sobrescribir (en POSIX `os.link` + `unlink`; en Windows `os.rename` falla si existe), verificación de duración y regla de «pesa más». *(AgentRelay, esfuerzo alto; revisado)*
- [x] 1.6 `core/runner.py` + tests: ejecución con progreso (`out_time_us`), velocidad, tiempo restante, pausa, cancelación sin huérfanos y prioridad baja. Errores de FFmpeg → `EncodeError(code, detail)` con códigos traducibles (sin espacio, archivo dañado, códec ausente, permiso denegado, desconocido). *(AgentRelay, esfuerzo xhigh; revisado. El ejecutor dejó archivos de validación fuera del código en el árbol de trabajo (caché pip, `runner-validation-*`, `encoded.mkv`); se limpiaron antes de aceptar)*
- [x] 1.7 `core/queue.py` + `core/report.py` + tests: cola secuencial, carpeta (recursiva opcional, filtro por extensión), progreso total ponderado por duración, eventos para la interfaz e informe de ahorro, errores y avisos. *(AgentRelay, esfuerzo alto; revisado, 1 reintento del propio ejecutor)*
- [ ] 1.8 `cli.py`:
  - Órdenes `reduvid probe <archivos>` (resumen legible) y `reduvid convert <archivos|carpeta> --target --quality --container --max-height --output-dir --recursive --threads --replace-original --dry-run`.
  - Códigos de salida documentados.
  - Configuración en `platformdirs.user_config_dir("reduvid")` (TOML de lectura con `tomllib` y escritura propia mínima).
- [ ] 1.9 Tests de integración (marcador `ffmpeg`): `tests/conftest.py` genera vídeos con lavfi (testsrc2 + 2 audios sine con idioma + srt + capítulos por ffmetadata; una variante de 10 bits) y prueba convertir, verificar, no sobrescribir y cancelar sin huérfanos. CI instala FFmpeg (apt; en Windows con `choco install ffmpeg` o una acción equivalente).
- [ ] 1.10 Docs y versión 0.1.0: uso de la CLI en README/README.en y `docs/{es,en}/cli.md`, y CHANGELOG. *(Sonnet, esfuerzo bajo)*

## Fase 2: interfaz y asistente (0.2.0)

Se detalla con más precisión al llegar (lo hará Opus, a partir de las maquetas de `docs/design/mockups.html`). Contenido:

- Sistema de **tres temas** por tokens → QSS, con claro y oscuro cada uno: **Plegat** (por defecto), **Riso** y **Cinta**. Selector de tema en Preferencias; persistido en la configuración del usuario.
- Tipografías OFL incluidas en `src/reduvid/resources/fonts/` con su licencia (Bricolage Grotesque e Instrument Sans para Plegat; Archivo y Atkinson Hyperlegible para Riso; Barlow/Barlow Condensed y JetBrains Mono para Cinta).
- Modos Asistente y Avanzado: elegir vídeos, destino, calidad, qué conservar, salida y resumen con semáforo Jellyfin.
- «¿Qué es esto?» en cada opción, errores traducidos con «ver detalles técnicos», pantalla de FFmpeg ausente e i18n ca/es/en.
- Accesibilidad: teclado, contraste y escalado.
- Capturas en `docs/` de cada tema, en claro y oscuro.

## Fase 3: ayudas (0.3.0)

Muestra de 30 s (en el 40 % del vídeo) con estimación y comparación de fotograma antes/después, estimación de tamaño y tiempo, informe final, perfiles guardados y avisos de HDR, 10 bits y subtítulos de imagen en la interfaz.

## Fase 4: empaquetado y publicación (0.4.0 → 1.0.0)

- pipx/PyPI.
- Windows: PyInstaller en modo carpeta (Qt queda reemplazable, como exige la LGPL) + instalador Inno Setup.
- Linux: AppImage; evaluar .deb y Flatpak.
- CI de artefactos, capturas, revisión final de licencias y primera release (con OK).

## Decisiones resueltas (histórico)

- **Contribuciones externas de código:** se exigirá **DCO** (Developer Certificate of Origin), no un CLA. Quien contribuye certifica con `Signed-off-by` en el commit que el código es suyo y lo aporta bajo WNCL-CU-1.0; no hay cesión de derechos a Catlinux ni papeleo aparte. Es el mínimo habitual en proyectos pequeños de un solo mantenedor; un CLA sería desproporcionado aquí. Pendiente de aplicar en `CONTRIBUTING.md`/`.en.md` (quitar el bloqueo de PRs de código y explicar el DCO) cuando se abra el repositorio a contribuciones.

## Dudas abiertas

- Adjuntos y portada en MKV (mencionado en 1.4): `MediaInfo` (paso 1.2) no expone streams de tipo `attachment`. Falta decidir si se añade a `probe.py` o se trata aparte antes de cerrar la Fase 1.
