# Elegir pistas y reducir el audio

Estado: `[x]` hecho · `[ ]` pendiente. Ante un imprevisto de diseño, **para** y anótalo en «Dudas abiertas». Convenciones: `CLAUDE.md`. Cada paso: tests, textos por `_()` (ca/es/en), docs es/en y entrada en `## [Sin publicar]` de ambos CHANGELOG. La versión sube solo en el último paso.

## Problema

El paso «Qué conservar» elige solo por idioma para toda la cola. Un vídeo con dos pistas en español (p. ej. E-AC3 640k + AC3 640k, ~0,7 GB cada una en 2 h 25 min) conserva ambas, y el audio puede ser casi la mitad del archivo. El asistente tampoco explica cuánto pesa cada parte ni qué admite cada contenedor.

## Decisiones (usuario, 26-10-2026)

- **Elegir pistas:** con **1 vídeo**, lista pista a pista con casilla (idioma, códec, canales, tamaño estimado). Con **varios**, reglas por idioma + casilla «solo una pista por idioma» (se queda la mejor: más canales, luego mayor bitrate, luego la marcada por defecto).
- **Reducir el audio:** casilla en el mismo paso. Recodifica a AAC (compatible con MP4 y MKV) a un bitrate por canales (aprox. 256 kbps en 5.1, 128 kbps en estéreo). Por defecto desactivada: hoy AAC/AC3/E-AC3 se copian.
- **Tamaños por pista** estimados con bitrate × duración; si falta bitrate, «—». Es una estimación y se rotula como tal.
- **Contenedor y subtítulos:** el paso explica en una línea que MP4 admite subtítulos de texto (se convierten a `mov_text`) pero no los de imagen (PGS/VobSub), que solo caben en MKV. Si hay subtítulos de imagen y el contenedor es MP4, aviso visible antes de elegir.

## Pasos

- [x] 1 **Motor.** *AgentRelay, esfuerzo alto.* Archivos: `core/plan.py`, `core/probe.py` (bitrate por pista si falta, `tags BPS`), tests de plan.
  - `PlanOptions`: `audio_tracks: frozenset[int] | None` (índices de ffprobe; `None` = filtro por idioma como hasta ahora), `one_audio_per_language: bool = False`, `reduce_audio: bool = False`.
  - Función pura `estimate_stream_bytes(stream, duration)` en el motor y `rank_audio(streams)` para elegir «la mejor».
  - `reduce_audio` → decisión `encode` a `aac` con el bitrate indicado, aviso `audio_reduced`; sin él, la política actual.
  - Terminado: tests con un vídeo de 2 audios es + 1 en, los tres modos y el caso «ninguna pista seleccionada» (conserva todas y avisa, como ahora).
- [x] 2 **CLI.** *AgentRelay, esfuerzo medio.* `reduvid-cli`: `--audio-tracks 1,3`, `--one-audio-per-language`, `--reduce-audio`; `probe` muestra el tamaño estimado por pista. Documentado en `docs/{es,en}/cli.md`.
- [x] 3 **Estado del asistente.** *AgentRelay, esfuerzo alto.* `gui/wizard_state.py` y `wizard_logic.py`: selección por pista (solo con 1 vídeo), las dos casillas nuevas, estimación del peso final por partes (vídeo según calidad no, solo pistas). Sin Qt en la lógica nueva y con tests.
- [x] 4 **Interfaz del paso.** *Sesión Sonnet/Opus, esfuerzo medio (diseño visual), con `docs/design/mockups.html` y los tres temas.* `gui/wizard/step_keep.py`: tabla/lista de pistas con tamaño, casillas, aviso de contenedor, `WhatIsThis` actualizado. Capturas nuevas en `docs/screenshots/` y `docs/{es,en}/gui.md`.
- [x] 5 **Traducciones y cierre.** *AgentRelay, esfuerzo medio.* `.pot`, ca/es, `messages.py` para `audio_reduced`; versión **0.3.0** (funcionalidad nueva compatible), CHANGELOG es/en, README/TODO (la antigua «0.3.0, ayudas» pasa a 0.4.0).

## Dudas abiertas

- Bitrate AAC por canales y «la mejor pista»: valores propuestos; confirmar al probar con la película de Spider-Man (`~/Descargas`, 6,7 GB → ~3,1 GB con H.265).
- Reparto del trabajo si la película debe volver a convertirse: tras el paso 1 ya se puede probar por CLI.
