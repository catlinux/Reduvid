# Registro de cambios

**Castellano** · [English](CHANGELOG.en.md)

Todos los cambios relevantes de Reduvid se documentan aquí. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Añadido

- Esqueleto de la interfaz gráfica: ventana principal con barra superior, conmutador Asistente/Avanzado, paneles de pasos, contenido y cola (apilados en ventanas estrechas), diálogo de preferencias (tema, modo de color, idioma, animaciones y ruta de FFmpeg con comprobación) y pantalla de ayuda cuando falta FFmpeg.

- Configuración de usuario en `core/config.py`: lectura TOML (con la ruta de FFmpeg en la raíz o en `[ffmpeg] path`, claves desconocidas ignoradas y lista de claves inválidas) y escritura atómica propia.
- Tipografías de la interfaz (Bricolage Grotesque, Instrument Sans, Archivo, Atkinson Hyperlegible, Barlow, Barlow Condensed y JetBrains Mono), con licencia SIL OFL 1.1 y su `OFL.txt`; documentadas en `THIRD_PARTY_NOTICES.md`.
- Procesado por archivo compartido en `core/pipeline.py`, con pausa, reanudación y cancelación, y errores con código (`cancelled` y `verification_failed`); la cola de conversión informa además del código de error de cada archivo.
- Traducción con gettext en el motor y la línea de órdenes: `reduvid/i18n.py` (idioma efectivo desde `--lang`, la configuración o el sistema), `reduvid/messages.py` con textos claros para cada aviso y error, catálogos `ca` y `es` con el `.pot` de referencia, y la orden global `--lang {ca,es,en}`.
- Scripts de desarrollo para extraer y compilar las traducciones, y un hook de Hatch que compila los `.po` a `.mo` al instalar en editable y al construir el wheel.
- Filtro por idioma para audio y subtítulos (`--keep-audio`, `--keep-subs`) y semáforo de compatibilidad con Jellyfin en `core/compat.py` (`direct`, `partial`, `blocked`), con avisos nuevos para el perfil de destino y el vídeo de 10 bits.
- Temas de la interfaz: tokens exactos de Plegat, Riso y Cinta en claro y oscuro (`gui/theme/tokens.py`), hoja de estilos generada desde ellos (`qss.py`), registro de las fuentes incluidas (`fonts.py`) y `ThemeManager` para aplicar tema y modo, incluido el del sistema.
- Trabajo en segundo plano y panel de cola: sondeo y conversión en hilos propios con señales Qt, progreso con tiempo restante, pausa y reanudación, cancelación sin archivos a medias, fichas de aviso por vídeo, total estimado, vista de error con detalles técnicos y confirmación al cerrar con una conversión en marcha.

### Cambiado

- `reduvid` abre ahora la interfaz gráfica y la línea de órdenes pasa a ser `reduvid-cli`; la documentación de uso se ha actualizado.

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
