# Registro de cambios

**Castellano** · [English](CHANGELOG.en.md)

Todos los cambios relevantes de Reduvid se documentan aquí. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.3.0] - 2026-10-25

### Añadido

- Motor de muestra y estimación: recorte rápido de un fragmento de 30 s reutilizando el plan de codificación (`-ss` antes de `-i`), extracción de un fotograma PNG y extrapolación lineal de tamaño y tiempo de conversión desde la muestra.
- Perfiles guardados en el motor: `core/profile_store.py` con lista, carga, guardado atómico y borrado de perfiles TOML individuales en la carpeta de configuración, conservando los nombres reales y la diferencia entre idiomas sin filtrar y conjunto vacío.
- Muestra y comparación en el paso Calidad: botón para probar 30 s en segundo plano, fotogramas antes/después, tamaño total estimado, porcentaje de ahorro e invalidación al cambiar la calidad; los temporales usan nombres fijos en la caché.
- Estimación en el paso Resumen: si hay una muestra vigente para la calidad elegida, cada tarjeta muestra tamaño y tiempo estimados extrapolados a su duración; sin muestra no se muestra ningún dato.
- Perfiles guardados desde el paso Calidad: desplegable para aplicar un perfil completo y diálogo para guardar la combinación actual con nombre, con errores visibles y sin crear nada si el nombre está vacío.
- Empaquetado para Windows con PyInstaller en modo carpeta (`--onedir`) mediante `packaging/windows/reduvid.spec` y `scripts/build_windows.py`, con las fuentes y traducciones incluidas, el icono en el ejecutable y en las ventanas, y FFmpeg siempre externo.
- Avisos tempranos en el paso Calidad: el primer vídeo disponible muestra los avisos del plan (HDR, 10 bits, subtítulos de imagen, etc.) antes de llegar al Resumen, recalculados al cambiar las opciones o los vídeos.

## [0.2.1] - 2026-10-25

### Cambiado

- Botones principales con `role=primary` (Empezar, Siguiente y Elegir ffmpeg) y Cancelar de la cola con `role=danger`, en vez del mismo estilo plano que el resto de botones; la sombra desplazada de Riso se aplica también a los botones primarios y las tarjetas de opción recomendadas muestran un fondo tintado.
- En el paso Resumen, cada vídeo pasa de una línea de texto con un badge pequeño a una tarjeta completa coloreada según el semáforo de compatibilidad con Jellyfin, y el hueco vertical que antes se repartía entre filas ahora queda agrupado en un solo bloque.

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
