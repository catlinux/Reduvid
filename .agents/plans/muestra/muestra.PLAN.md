# Prueba de muestra: estimar tamaño y tiempo antes de convertir

Estado: `[x]` hecho · `[ ]` pendiente. Ante un imprevisto de diseño, **para** y anótalo en «Dudas abiertas». Convenciones: `CLAUDE.md`. Cada paso: tests, textos por `_()` (ca/es/en), docs es/en y entrada en `## [Sin publicar]` de ambos CHANGELOG. La versión sube a **0.4.0** solo en el último paso. Lo que quedaba de la antigua «0.4.0» (informe final, perfiles guardados, avisos en la interfaz) pasa a 0.5.0 y los instaladores a 0.6.0 → 1.0.0.

## Decisiones (usuario, 26-10-2026)

- La muestra es de **1 minuto en total, en 3 trozos de 20 s** hacia el 20 %, 50 % y 80 % del vídeo.
- Se mide **solo el vídeo** (`-an -sn`), con los mismos ajustes del plan (códec, CRF, preajuste, filtros, escala). El audio y los subtítulos ya se estiman por bitrate (`audio_size_summary`).
- Estimación = `bytes_muestra × 8 / segundos_muestra` (bitrate de vídeo) × duración total / 8, más audio y subtítulos. Tiempo = tiempo real de la muestra / segundos de muestra × duración total. Siempre rotulado como **estimación** (con margen orientativo, sin cifras inventadas).
- Vídeos cortos: si la duración es < 90 s, se usa un único trozo con todo el vídeo (máx. 60 s desde el inicio). Los trozos nunca se solapan ni pasan del final.
- Los temporales de la muestra van a un directorio temporal propio y se borran siempre (también al cancelar). Nunca se toca el original ni la carpeta de destino.

## Pasos

- [x] 1 **Motor.** *AgentRelay, esfuerzo alto.* `core/sample.py` + tests (puros y uno de integración con marcador `ffmpeg`).
  - `sample_segments(duration, count=3, length=20.0, fractions=(0.2, 0.5, 0.8)) -> tuple[SampleSegment, ...]` (start, length).
  - `build_sample_command(plan, input_path, output_path, segment) -> list[str]`: `-ss` antes de `-i`, `-t`, solo el primer vídeo del plan con sus ajustes (reutiliza la lógica de `command.build_command`, extrayendo lo común en vez de copiar), `-an -sn`, sin metadatos ni capítulos.
  - `run_sample(...)`: ejecuta los trozos en serie con `EncodeHandle` (prioridad baja, cancelable, progreso agregado 0-1), calcula `SampleEstimate(video_bytes, seconds_per_second, sampled_seconds)` y borra los temporales. Errores como `EncodeError`.
  - `estimate_total(sample, media, audio_bytes, subtitle_bytes=None) -> TotalEstimate(video_bytes, audio_bytes, total_bytes, ratio_vs_original, encode_seconds)`.
- [x] 2 **CLI.** *AgentRelay, esfuerzo medio.* `reduvid-cli estimate <archivo> [mismas opciones que convert]`: ejecuta la muestra con progreso en texto y muestra tamaño estimado total (vídeo, audio), ahorro frente al original y tiempo aproximado; `--dry-run` no aplica. Documentado en `docs/{es,en}/cli.md`.
- [x] 3 **Asistente.** *AgentRelay, esfuerzo alto.* Paso «Resumen»: por cada vídeo, botón «Estimar el tamaño final (prueba de 1 minuto)» con barra de progreso, botón Cancelar y resultado «Tamaño estimado: ~X GB (de 6,7 GB: −Y %) · Tiempo aprox.: Z». Worker en hilo aparte (patrón de `gui/workers.py`); el resultado se invalida si cambian opciones, calidad, destino o pistas. Sin Qt en la lógica nueva; tests offscreen.
- [ ] 4 **Cierre.** *Sesión.* Versión 0.4.0, CHANGELOG es/en, README y TODO (hoja de ruta), `docs/{es,en}/gui.md`, traducciones al día.

## Fuera de alcance (a `TODO.md`)

- Comparación de fotograma antes/después.
- Mostrar el tamaño estimado en las tarjetas del paso «Calidad» (requeriría una muestra por nivel).

## Dudas abiertas

- Margen de error real de la estimación: medirlo con la película de prueba (`~/Descargas`) comparando con la conversión completa antes de afirmar una cifra en la documentación.
