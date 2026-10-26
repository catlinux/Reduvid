# Registro de cambios

**Castellano** · [English](CHANGELOG.en.md)

Todos los cambios relevantes de Reduvid se documentan aquí. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.5.1] - 2026-10-26

### Añadido

- La interfaz activa `faulthandler`: si hay un fallo nativo (por ejemplo «Error del bus»), imprime en la terminal en qué línea estaba cada hilo de Python, para poder localizarlo.

## [0.5.0] - 2026-10-26

### Añadido

- Asistente, paso «Calidad»: cada tarjeta explica qué cambia (códec, resolución, HDR o 10 bits) y qué detalle se pierde; un botón estima el tamaño de los tres niveles con una muestra corta de 20 s por nivel, en segundo plano y cancelable; un selector de resolución (Automática, 1080p, 720p, 480p) y los «Detalles técnicos» plegados (códec, preajuste, CRF, perfil y formato de píxel).
- Motor: `estimate_levels` y `SampleLevelsRunner` (`core/sample.py`) estiman varios niveles de calidad; `SampleRunner` admite número y duración de trozos.

### Cambiado

- La altura máxima (`--max-height` y selector de resolución) se aplica en todos los perfiles; antes solo en `jellyfin`. Sin ella, `jellyfin` sigue bajando a 1080p y los demás perfiles conservan la resolución. Nunca se escala hacia arriba.
- El aviso de reducción de resolución es genérico («de 2160p a 1080p») en lugar de mencionar siempre 1080p.
- Asistente, paso «Destino»: cada opción indica su códec y su compromiso entre tamaño y compatibilidad.

## [0.4.0] - 2026-10-26

### Añadido

- Prueba de muestra: el motor convierte 3 trozos de 20 s (hacia el 20 %, 50 % y 80 % del vídeo) con los ajustes del plan, mide el vídeo y estima el tamaño final y el tiempo de conversión (`core/sample.py`).
- CLI: nueva orden `reduvid-cli estimate` con las mismas opciones de plan que `convert`.
- Asistente, paso «Resumen»: botón «Estimar el tamaño final (prueba de 1 minuto)» por vídeo, con progreso, cancelación y resultado; se descarta si cambian los ajustes.

## [0.3.0] - 2026-10-26

### Añadido

- Motor: selección de audio por pista (`audio_tracks`), «una pista por idioma» (`one_audio_per_language`), reducción del audio a AAC (`reduce_audio`), bitrate por pista en el sondeo y estimación de su tamaño.
- CLI: opciones `--audio-tracks`, `--one-audio-per-language` y `--reduce-audio` en `convert`, y tamaño estimado de cada pista de audio en `probe` y `--dry-run`.
- Asistente, paso «Qué conservar»: con un solo vídeo se elige el audio pista a pista (idioma, formato, canales y peso estimado), casilla «Una sola pista de audio por idioma», casilla «Reducir el peso del audio» con el resumen «el audio pasa de X a Y» y aviso de qué subtítulos admite cada contenedor.

## [0.2.1] - 2026-10-26

### Corregido

- Instalación del README y de CONTRIBUTING: usa `python3` (en Debian no existe `python`) y activa el entorno virtual antes de `pip install`, que fallaba con `externally-managed-environment`.

## [0.2.0] - 2026-10-25

### Añadido

- Guía de uso de la interfaz en `docs/es/gui.md` y `docs/en/gui.md`.
- Esqueleto de la interfaz gráfica: ventana principal con barra superior, conmutador Asistente/Avanzado, paneles de pasos, contenido y cola (apilados en ventanas estrechas), diálogo de preferencias (tema, modo de color, idioma, animaciones y ruta de FFmpeg con comprobación) y pantalla de ayuda cuando falta FFmpeg.

- Configuración de usuario en `core/config.py`: lectura TOML (con la ruta de FFmpeg en la raíz o en `[ffmpeg] path`, claves desconocidas ignoradas y lista de claves inválidas) y escritura atómica propia.
- Tipografías de la interfaz (Bricolage Grotesque, Instrument Sans, Archivo, Atkinson Hyperlegible, Barlow, Barlow Condensed y JetBrains Mono), con licencia SIL OFL 1.1 y su `OFL.txt`; documentadas en `THIRD_PARTY_NOTICES.md`.
- Procesado por archivo compartido en `core/pipeline.py`, con pausa, reanudación y cancelación, y errores con código (`cancelled` y `verification_failed`); la cola de conversión informa además del código de error de cada archivo.
- Traducción con gettext en el motor y la línea de órdenes: `reduvid/i18n.py` (idioma efectivo desde `--lang`, la configuración o el sistema), `reduvid/messages.py` con textos claros para cada aviso y error, catálogos `ca` y `es` con el `.pot` de referencia, y la orden global `--lang {ca,es,en}`.
- Scripts de desarrollo para extraer y compilar las traducciones, y un hook de Hatch que compila los `.po` a `.mo` al instalar en editable y al construir el wheel.
- Filtro por idioma para audio y subtítulos (`--keep-audio`, `--keep-subs`) y semáforo de compatibilidad con Jellyfin en `core/compat.py` (`direct`, `partial`, `blocked`), con avisos nuevos para el perfil de destino y el vídeo de 10 bits.
- Temas de la interfaz: tokens exactos de Plegat, Riso y Cinta en claro y oscuro (`gui/theme/tokens.py`), hoja de estilos generada desde ellos (`qss.py`), registro de las fuentes incluidas (`fonts.py`) y `ThemeManager` para aplicar tema y modo, incluido el del sistema.
- Trabajo en segundo plano y panel de cola: sondeo y conversión en hilos propios con señales Qt, progreso con tiempo restante, pausa y reanudación, cancelación sin archivos a medias, fichas de aviso por vídeo, total estimado, vista de error con detalles técnicos y confirmación al cerrar con una conversión en marcha.
- Asistente, pasos 1-3: estado compartido del asistente, tarjetas de opción accesibles, lista de pasos hechos/actual/pendiente, navegación Atrás/Siguiente, alta de vídeos con arrastrar y soltar y sondeo en segundo plano, selección de destino (con «No lo sé») y de calidad con recomendación según el destino y explicación del CRF.
- Asistente, pasos 4-6: selección de idiomas de audio y subtítulos con nombres legibles, carpeta de salida, contenedor, reemplazo del original y reducción de 4K, resumen por vídeo con semáforo de compatibilidad, diálogo para los vídeos HDR bloqueantes, arranque de la conversión e informe final con errores y vídeos saltados.
- Modo Avanzado: una sola página con todas las opciones de la CLI (vídeos, destino, calidad, contenedor, altura máxima, carpeta de salida, hilos, reemplazo, idiomas y resumen con arranque), compartiendo el estado del asistente; el conmutador conserva la selección, guarda `ui_mode` y se bloquea durante una conversión.
- Accesibilidad: nombre accesible en todos los controles interactivos, orden de tabulación por página, atajos Alt+ coherentes en los botones principales (también en catalán y castellano), foco visible en todos los controles de los seis temas y textos largos con ajuste de línea al aumentar la fuente.
- Motivos pintados propios de cada tema: esquina doblada, barra en acordeón y gato de origami en Plegat; sombra desplazada, pista tramada, gato y cifra con eje variable en Riso; franja de tres colores, bobinas y contador mecánico en Cinta. La barra de progreso de la cola se pinta a mano desde los tokens y no usa temporizadores, por lo que respeta «Reducir animaciones».
- Capturas de la interfaz en `docs/screenshots/` (los tres temas, claro y oscuro), enlazadas desde el README y la guía de la interfaz.

### Cambiado

- `reduvid` abre ahora la interfaz gráfica y la línea de órdenes pasa a ser `reduvid-cli`; la documentación de uso se ha actualizado.
- La interfaz fuerza el estilo Qt Fusion para que el anillo de foco y el resto de la hoja de estilos se apliquen igual en todas las plataformas, en vez de depender del estilo nativo.

### Corregido

- El tamaño inicial de la ventana se ajusta a la pantalla disponible, para que un escalado alto (150 %, 200 %) no la deje más ancha que el escritorio.
- Dos textos en catalán que usaban «guardar» en vez de «desar», para ser consistentes con el resto del catálogo.

## [0.1.0] - 2026-10-24

### Añadido

- Motor de conversión (`reduvid.core`), sin dependencias de Qt: detección de FFmpeg y sus capacidades, sondeo con ffprobe (vídeo, audio, subtítulos, capítulos, adjuntos y portada, HDR10/HLG/Dolby Vision), perfiles de destino (`jellyfin`, `modern`, `archive`) y plan de codificación por pista con avisos tipados, construcción de los argumentos de FFmpeg, nombrado de salida sin colisiones ni sobrescritura, verificación de duración y tamaño tras convertir, y ejecución controlada con progreso, pausa, cancelación sin huérfanos y prioridad baja.
- Cola de conversión secuencial con progreso ponderado por duración e informe final de ahorro.
- Línea de órdenes: `reduvid probe` (resumen legible de un vídeo) y `reduvid convert` (conversión con `--target`, `--quality`, `--container`, `--max-height`, `--output-dir`, `--recursive`, `--threads`, `--replace-original` y `--dry-run`), con lectura de la ruta de FFmpeg desde un archivo de configuración si no está en el `PATH`.
- Tests de integración de extremo a extremo con FFmpeg real (vídeos generados con `lavfi`), además de la suite unitaria de cada módulo del motor.
- Guía de uso de la línea de órdenes en castellano e inglés (`docs/{es,en}/cli.md`).
- Capturas de las maquetas de diseño en el README.

## [0.0.1] - 2026-10-24

### Añadido

- Estructura inicial del proyecto: paquete Python con `reduvid --version`, tests, ruff, mypy, pre-commit e integración continua en Linux y Windows.
- Licencia WNCL-CU-1.0, autoría y avisos de terceros.
- Documentación base en castellano e inglés (README, CHANGELOG, TODO, guía de contribución, seguridad y código de conducta) y comprobación automática de que ambas versiones tienen la misma estructura.
- Hoja de ruta por fases y maquetas de tres direcciones de diseño: Riso, Cinta y Plegat (elegidas como temas intercambiables, con Plegat por defecto).
- Política de contribuciones de código bajo DCO (Developer Certificate of Origin).
