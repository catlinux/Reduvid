# Opciones de vídeo claras: qué se reduce y qué se pierde

Estado: `[x]` hecho · `[ ]` pendiente. Ante un imprevisto de diseño, **para** y anótalo en «Dudas abiertas». Convenciones: `CLAUDE.md`. Cada paso: tests, textos por `_()` (ca/es/en), docs es/en y entrada en `## [Sin publicar]` de ambos CHANGELOG. La versión sube a **0.5.0** solo en el último paso (la antigua 0.5.0 «informe final, perfiles guardados, avisos» pasa a 0.6.0 y los instaladores a 0.7.0 → 1.0.0).

## Problema (queja del usuario, 26-10-2026)

Las opciones de vídeo son pocas y ambiguas: las tarjetas de calidad no dicen cuánto se ahorra ni qué se pierde, el destino no explica que decide el códec, y no hay control de resolución. Hoy:
- `core/profiles.py`: perfiles `jellyfin` (x264, high@4.1, yuv420p), `modern` y `archive` (x265, preset medium/slow); CRF por calidad en `QUALITY_CRFS`.
- `core/plan.py::_video_decision`: la reducción de resolución **solo** ocurre en `jellyfin` (`should_reduce = jellyfin and ...`) y el aviso se llama `resolution_reduced_4k_to_1080p` aunque `max_height` sea otro valor. HDR→SDR solo en jellyfin.
- `WizardState.max_height` existe pero la interfaz no lo expone.
- `core/sample.py` ya estima tamaño/tiempo de una combinación de ajustes (3×20 s).

## Decisiones (usuario, 26-10-2026)

- Alcance completo: tamaños estimados en las tarjetas de calidad, bloque «qué cambia» en cada opción, selector de resolución y detalles técnicos plegados.

## Pasos

- [x] 1 **Motor: resolución para cualquier perfil.** *AgentRelay, esfuerzo medio.* `core/plan.py`: `max_height` se aplica en todos los perfiles (hoy solo jellyfin); si el vídeo ya es menor o igual, no se toca ni se escala hacia arriba. Aviso `resolution_reduced` con `from_height`/`to_height` (mantener el código antiguo solo si hay tests que lo requieran; actualizar `messages.py` y la CLI). Opción `--max-height` en `convert`/`estimate` si no existe. Altura par (el ancho se calcula con `-2`). Tests de plan y comando.
- [x] 2 **Motor: estimación por nivel.** *AgentRelay, esfuerzo alto.* En `core/sample.py`, `estimate_levels(media, ffmpeg_info, options, qualities=("high","balanced","max_savings"), segments=1, length=20.0)` que devuelve un `TotalEstimate` por nivel (una sola pasada de 20 s por nivel, cancelable, progreso agregado). Reutiliza `run_sample`/`estimate_total`. Tests con marcador `ffmpeg` y puros.
- [x] 3 **Textos y datos de «qué cambia».** *Sesión (decisión de redacción).* En `gui/wizard_logic.py`, función pura `change_notes(destination, quality, media_list) -> tuple[str, ...]` con viñetas concretas y verificables (códec y compatibilidad; resolución resultante; HDR→SDR sí/no; 8/10 bits; «detalle que se pierde» por nivel sin cifras inventadas). Sin jerga sin explicar; el CRF solo en los detalles técnicos.
- [ ] 4 **Asistente.** *AgentRelay, esfuerzo alto.* (a) Paso «Calidad»: cada tarjeta muestra «~X GB (−Y %)» y las viñetas de `change_notes`; las estimaciones se calculan en un worker al entrar (solo con un vídeo; con varios, estimar el primero o el más largo y rotularlo así), con estado «calculando…», cancelables y reutilizables mientras no cambien destino/pistas/resolución. (b) Selector de resolución («Mantener», «1080p», «720p», solo opciones menores que el original) en «Calidad» o paso propio, con efecto en las estimaciones. (c) Bloque plegable «Detalles técnicos» con códec, preset, CRF, perfil/nivel y píxel. (d) El paso «Destino» dice qué códec implica cada opción y su compromiso (tamaño vs compatibilidad). Tests offscreen; capturas con `docs/screenshots/` si procede.
- [ ] 5 **Cierre.** *Sesión.* Versión 0.5.0, CHANGELOG es/en, README (hoja de ruta), TODO (quitar «tamaño en tarjetas»), `docs/{es,en}/gui.md` y `cli.md`, `reduvid.pot`/`.po`/`.mo` al día, ruff/mypy/pytest/`check_doc_sync`.

## Fuera de alcance (a `TODO.md`)

- Comparación de fotograma antes/después.
- Control de fotogramas por segundo y de audio multicanal avanzado.

## Dudas abiertas

- ¿Cuánto tarda estimar tres niveles en vídeos 4K en este equipo? Medirlo en el paso 2; si pasa de ~1 min, estimar solo «Equilibrada» y extrapolar con la relación de CRF medida, y anotarlo aquí.
- Margen de error real de la estimación (pendiente desde `muestra`): comparar con una conversión completa antes de dar cifras en la documentación.
