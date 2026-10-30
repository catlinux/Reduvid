# Registro de cambios

**Castellano** · [English](CHANGELOG.en.md)

Todos los cambios relevantes de Reduvid se documentan aquí. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.9.1] - 2026-10-30

### Cambiado

- En Windows, «Instalar ahora» vuelve a abrir Reduvid cuando termina la actualización. Con «Al cerrar» no se reabre.

### Corregido

- Al terminar la instalación en Windows, la app abierta por el instalador decía que no encontraba FFmpeg aunque estuviera instalado. La causa era que heredaba una variable `PATHEXT` sin `.EXE`, y `shutil.which` no encontraba entonces el ejecutable; ahora se busca `ffmpeg.exe` directamente en cada carpeta del PATH y del registro.

## [0.9.0] - 2026-10-30

### Añadido

- **Actualizaciones automáticas desde GitHub.** Reduvid comprueba como mucho una vez al día si hay una release nueva (solo se envía la petición, sin datos de uso), con un aviso explicativo la primera vez y una casilla en Preferencias para desactivarlas. Si hay versión nueva, una franja ofrece «Qué cambia», «Instalar ahora», «Al cerrar» y «Ahora no». La descarga es solo por HTTPS y se verifica con `SHA256SUMS`. Con el instalador de Windows se actualiza sobre la misma instalación sin pedir administrador; con el AppImage se reemplaza el archivo; desde el código fuente solo abre la página de la release. Nunca interrumpe una conversión.

### Corregido

- El catálogo de traducciones salía distinto según la versión de Python (3.11 no extraía las cadenas escritas dentro de un f-string), lo que ponía el CI de Linux en rojo.
- La detección de rutas absolutas de Windows fallaba al ejecutar los tests con Python 3.11 en Linux, y el CI de Linux seguía en rojo.
- Si la app arrancada por el instalador de Windows decía que no encontraba FFmpeg aunque estuviera instalado, ahora la pantalla muestra los «Detalles técnicos» de la búsqueda (qué rutas encontró y el error al lanzar FFmpeg) para poder diagnosticarlo. Además, los procesos hijos se lanzan con la entrada estándar cerrada, por si el fallo venía de manejadores heredados; no está comprobado que sea la causa.
- El CI de Linux fallaba al recolectar los tests de la interfaz porque el runner no traía las librerías del sistema que necesita Qt (`libEGL`); ahora se instalan y los tests corren con la plataforma `offscreen`.

## [0.8.3] - 2026-10-29

### Cambiado

- Las herramientas de desarrollo acotan ruff a la serie 0.15 para que el CI no falle cuando sale una versión nueva con reglas distintas.
- El instalador de Windows pasa a ser una instalación por usuario, sin pedir permisos de administrador. Quien tenga la 0.8.0 instalada en `Program Files` debe desinstalarla una vez a mano.

### Añadido

- Workflow de GitHub Actions que, al subir un tag `vX.Y.Z`, genera el instalador y el AppImage, publica `SHA256SUMS` y crea la release con las notas del CHANGELOG.

## [0.8.2] - 2026-10-28

### Corregido

- El panel de la cola tenía el mismo defecto que el Resumen: con varios vídeos y avisos, las filas se aplastaban y se pisaban. Ahora tiene su propio scroll.

## [0.8.1] - 2026-10-27

### Corregido

- El paso Resumen del asistente se veía mal con varios vídeos: las filas se aplastaban y se pisaban (el botón de estimar tapaba el título). Ahora la lista tiene su propio scroll y cada fila conserva su altura.

## [0.8.0] - 2026-10-27

### Cambiado

- **Cinecat sustituye a Jellyfin** como destino por defecto (`cinecat`). Cinecat solo reproduce directamente MP4 en el navegador, así que con este destino el contenedor automático es MP4; el vídeo sigue en H.264 High@4.1 de 8 bits, hasta 1080p y con el HDR pasado a SDR. El audio se copia si ya es AAC o MP3; si no, se recodifica a AAC (384k en 5.1, 192k en estéreo, hasta 6 canales), porque Chrome y Firefox no reproducen AC-3/E-AC-3. Los subtítulos de imagen se descartan con aviso.
- El semáforo de compatibilidad mide ahora la reproducción directa en Cinecat.
- Interfaz, avisos y CLI hablan de Cinecat en lugar de Jellyfin (ca, es, en). Con destino Cinecat, el paso Destino recomienda MP4 y explica que el MKV se convertirá al verlo.
- El contenedor pasa a ser automático por defecto (MP4 para Cinecat, MKV para los demás destinos).
- Las configuraciones y los perfiles guardados con `destination = "jellyfin"` se leen como `cinecat`; el `container = "mkv"` que guardaban por defecto vuelve a automático.

### Añadido

- Motor: `core/updates.py` comprueba si hay una release más nueva en GitHub (como mucho una vez al día, sin enviar datos), descarga el instalador o el AppImage solo por HTTPS y lo verifica con `SHA256SUMS`. La interfaz que lo usa llegará en 0.9.0.
- La versión se ve en el título de la ventana y en Preferencias.
- «Qué conservar» muestra el peso de cada pista de subtítulos (de las etiquetas que escribe MKVToolNix), y los tamaños pequeños se muestran en KB.
- Al marcar «Una sola pista de audio por idioma», las casillas de las pistas muestran cuáles se conservarán y el tamaño del audio se recalcula; al desmarcarla vuelve la selección anterior, y tocar una pista a mano la desmarca.
- Los MP4 se escriben con `+faststart`, para que el navegador empiece a reproducir sin descargar el final del archivo.

### Corregido

- La página Avanzado no tenía márgenes y su contenido tocaba los bordes de la ventana.
- **La conversión de HDR a SDR no convertía los colores**: se aplicaba `zscale,tonemap` sin parámetros y el archivo seguía marcado como HDR, así que los reproductores mostraban los colores mal. Ahora se linealiza, se pasa a BT.709 con *tone mapping* Hable y la salida se marca como BT.709. Además se reduce la resolución antes del *tone mapping*, que en un 4K trabaja con cuatro veces menos píxeles.
- **En Windows 11 con procesadores híbridos (núcleos de rendimiento y de eficiencia) las conversiones iban unas tres veces más lentas**: al lanzar FFmpeg con prioridad baja, Windows lo trataba como trabajo de fondo y lo dejaba solo en los núcleos de eficiencia (4 de 16 hilos en un i5-14400F). La prioridad sigue siendo baja para que el equipo vaya fluido, pero ahora se pide a Windows que no limite el proceso y usa todos los núcleos.
- En Windows, la aplicación instalada abría ventanas de consola vacías delante del programa cada vez que lanzaba FFmpeg o ffprobe (por ejemplo, al estimar el tamaño). Ahora los procesos se lanzan sin ventana.
- La barra de progreso retrocedía al final de los MP4 mientras FFmpeg movía el índice al principio (`+faststart`).

### Eliminado

- El destino `jellyfin` y `reduvid-cli --target jellyfin`.

## [0.7.1] - 2026-10-27

### Cambiado

- Interfaz: los temas ganan los tokens y las reglas de estilo del rediseño (barra lateral, tarjeta elegida, etiquetas, chips, controles segmentados, títulos y barra de la cola), con tests de contraste de 4,5:1 en los tres temas y en los dos modos de color. Todavía no cambia ninguna pantalla.

### Corregido

- El CI fallaba en Linux en el paso de mypy por las llamadas al registro de Windows de la detección de FFmpeg.

## [0.7.0] - 2026-10-27

### Añadido

- Si el equipo tiene tarjeta gráfica, el vídeo original se lee con ella (`-hwaccel auto`), lo que libera el procesador para codificar; el resultado es el mismo. Si FFmpeg falla al usarla, el vídeo se repite automáticamente con el procesador. Se aplica a las conversiones y a las pruebas de muestra, y se puede desactivar en Preferencias.
- Motor: `FFmpegInfo.hwaccels` con los métodos de aceleración que ofrece FFmpeg.
- Motor: `core/thumbnail.py` extrae una miniatura JPEG de cada vídeo (fotograma al 10 %) y la guarda en la caché del usuario; la usará la interfaz rediseñada.
- Motor: `core/hardware.py` comprueba qué codificadores por hardware (NVENC, QSV, VAAPI, AMF) funcionan de verdad codificando un fotograma con cada uno, con caché por versión de FFmpeg. FFmpeg los anuncia aunque el driver no los admita.
- Motor: `core/profile_store.py` guarda perfiles con nombre (destino, calidad, contenedor, altura máxima, idiomas y opciones de audio) como archivos TOML en la configuración del usuario. Los índices de pista no se guardan porque solo valen para un vídeo concreto.
- AppImage de Linux (`packaging/linux/`) y el job `build-linux` del CI, recuperados de la rama paralela de Windows; la guía de instaladores vuelve a explicar Linux. Pendiente de probar en un Debian real.
- CLI: `--no-hw-decode` en `convert` y `estimate`, y la clave de configuración `hw_decode = false`, para no usar la tarjeta gráfica.

## [0.6.1] - 2026-10-27

### Corregido

- Con FFmpeg 9 no se detectaba ningún filtro, porque `ffmpeg -filters` muestra dos columnas de banderas en vez de tres. Los vídeos HDR no se convertían a SDR (se avisaba de que faltaban `zscale` y `tonemap`, aunque estaban). También se ignora la leyenda (`=`) al leer codificadores y filtros.

## [0.6.0] - 2026-10-27

### Añadido

- Instalador de Windows: paquete de carpeta con PyInstaller (`packaging/windows/reduvid.spec`, `scripts/build_windows.py`, extra `build`) e instalador con Inno Setup (`packaging/windows/reduvid.iss`), con acceso en el menú Inicio, desinstalador y actualización sobre la versión anterior. FFmpeg sigue siendo externo. Guía en `docs/es/instalacion.md`.
- Icono de la aplicación (`resources/icon/`), en el ejecutable, el instalador y las ventanas.
- CI: el job `build-windows` genera el instalador y lo publica como artefacto.

### Corregido

- En Windows se detecta un FFmpeg recién instalado (por ejemplo con winget) sin cerrar sesión: si no está en el `PATH` del proceso, se busca también en el `PATH` del registro.
- Los tests de `build_sample_command` fallaban en Windows porque usaban rutas POSIX (`/videos/…`), que allí no son absolutas.

## [0.5.2] - 2026-10-27

### Corregido

- La interfaz se cerraba con «Error del bus» o «Violación de segmento» al estimar tamaños (por niveles de calidad o en el resumen), sobre todo con varios vídeos. Los hilos de trabajo se programaban para borrarse (`deleteLater`) mientras el paso aún esperaba por ellos; ahora los conserva el módulo `workers` hasta que Qt confirma que han terminado.

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
