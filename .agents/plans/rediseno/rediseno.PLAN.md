# Rediseño visual y mejoras hacia la 1.0

Estado: `[x]` hecho · `[ ]` pendiente · `[~]` en curso. El ejecutor marca cada paso. Ante un imprevisto de diseño, **para** y anótalo en «Dudas abiertas». Convenciones: `CLAUDE.md` y `AGENTS.md`.

Maqueta aprobable: https://claude.ai/artifact/ADqmDRoDWKx9JcdyoABB1X (privada; 6 pantallas: Calidad en claro y Resumen con la cola en oscuro, para Plegat, Riso y Cinta).

## Diagnóstico (capturas reales de 0.6.1, Windows)

- Son widgets estándar de Qt con color encima: botones-caja iguales en peso, lista de vídeos como texto plano, cola vacía permanente a la derecha, huecos sin jerarquía. Los tres temas comparten esos defectos.
- **Fallos visibles:** en «Calidad» el texto de las tarjetas se corta (altura fija) y la ventana crece a 778 px de alto; en «Resumen» la tarjeta de cada vídeo deja un hueco enorme entre nombre y tamaño; en «Avanzado» el contenido toca los bordes (sin márgenes).

## Decisiones tomadas

- Se mantienen **los tres temas completos**, cada uno con su personalidad (decisión del usuario, 2026-10-27). Estructura común; cada tema aporta tokens y un «pintor» propio.
- Estructura nueva común: barra lateral fija (logo, pasos, modo, preferencias), contenido con columna de contexto «Tu vídeo» a la derecha, navegación Atrás/Continuar al pie del contenido, y **barra de transporte** inferior a todo el ancho que hace de cola (sustituye a `QueuePanel` como columna).
- Sin sombras de QSS (no existen): la sombra desplazada de Riso, la esquina doblada de Plegat y las franjas de Cinta se pintan con `QPainter`.
- La gráfica se usa **si la hay** y, si falla, se vuelve a la CPU sin intervención (petición del usuario).
- **Maqueta de Plegat aprobada** (2026-10-27, «me gusta Plegat»). Se implementa primero la estructura común con Plegat; Riso y Cinta, después, sobre la misma estructura.
- **Modo «Rápido» con la gráfica: sí** (2026-10-27), pero solo se ofrece cuando `probe_hardware_encoders` confirma un codificador que funciona; si no hay ninguno, la opción no aparece y todo sigue por CPU. Paso A8.

## Fase A: motor y funciones (no depende de la maqueta)

- [x] **A1. Decodificar con la gráfica si la hay.** *(Hecho en 0.7.0, AgentRelay, revisado; probado con la CLI real convirtiendo un 4K de 10 bits en este PC con RTX 4060)* `core/ffmpeg.py`: `FFmpegInfo.hwaccels` desde `ffmpeg -hide_banner -hwaccels`. `core/command.py`: `build_command(..., hw_decode=False)` añade `-hwaccel auto` antes de `-i`. `core/pipeline.py`: `FileProcessor(hw_decode=True)`; si FFmpeg falla con `-hwaccel` (y no se canceló), reintenta una vez sin él. Igual en `build_sample_command`/`SampleRunner` para que la estimación de tiempo sea coherente. Tests sin FFmpeg real (mocks) y uno con marcador `ffmpeg`. *AgentRelay, esfuerzo medio.* Versión 0.7.0 (menor), CHANGELOG «Añadido».
- [x] **A2. Opción para desactivarlo.** *(Hecho en 0.7.0 en dos tareas de AgentRelay, revisadas: `Config.hw_decode`, `--no-hw-decode`, casilla en Preferencias aplicada a conversiones y muestras, traducciones y docs)* `Config.hw_decode: bool = True` (carga/guardado), `reduvid-cli --no-hw-decode`, casilla en Preferencias «Usar la tarjeta gráfica para leer los vídeos, si la hay», textos ca/es/en, docs `cli.md`/`gui.md` ES y EN. *AgentRelay, esfuerzo medio.* Va en 0.7.0 (sin subir versión otra vez si A1 no se ha publicado).
- [x] **A3. Comprobar de verdad los codificadores por hardware.** *(Hecho en 0.7.0, solo el motor: `probe_hardware_encoders`. En el PC Windows anuncia 19 y no funciona ninguno: i5-14400F sin gráfica integrada y driver NVIDIA antiguo. Mostrarlo en Preferencias queda para B5)* Hoy `hardware_encoders` solo lista lo que trae FFmpeg (aquí NVENC aparece pero el driver no lo admite). Función `probe_hardware_encoders(info) -> tuple[str, ...]` que codifica 1 fotograma de `lavfi` con cada uno y se queda con los que funcionan; con caché por ruta y versión de FFmpeg. Solo informa (Preferencias/CLI `--version` detallado); no se usa para codificar. *AgentRelay, esfuerzo medio.* 0.7.0.
- [x] **A4. Miniatura de cada vídeo.** *(Hecho en 0.7.0, solo el motor: `extract_thumbnail(ffmpeg_path, media, *, width, cache_dir, timeout)`; la interfaz la pedirá en B3/B5)* `core/thumbnail.py`: `extract_thumbnail(ffprobe_info, path, at_seconds) -> bytes` (un JPEG con `-ss` al 10 % y `-frames:v 1 -vf scale=320:-2`), en caché de usuario (`platformdirs`). La interfaz la pide en segundo plano. Necesaria para la maqueta («Tu vídeo» y filas de la lista). *AgentRelay, esfuerzo medio.* 0.7.0.
- [ ] **A5. Informe final.** Al acabar la cola: total ahorrado, vídeos correctos, fallidos con su motivo traducido (`EncodeError.code`, `PipelineError.code`) y botón «Abrir carpeta». El motor ya tiene `core/report.py`; falta la pantalla. *AgentRelay, esfuerzo alto.* 0.8.0.
- [~] **A6. Rescatar de la rama paralela de Windows** *((a) motor hecho en 0.7.0: `core/profile_store.py`; decisión: no guarda `audio_tracks` (índices de un archivo concreto) y prefija los nombres reservados de Windows. La integración en la interfaz, (b) y (c) se harán dentro de B5 para no programar dos veces las pantallas)* (segundo padre del merge `419e676`, commits hasta `35970a1`), reimplementándolo sobre la base actual, un commit por punto: (a) perfiles guardados (`core/profile_store.py` + paso Calidad), (b) avisos de compatibilidad tempranos en Calidad (HDR, 10 bits, subtítulos de imagen), (c) comparación antes/después de un fotograma en la prueba de muestra. Leer el código antiguo con `git show 35970a1:<ruta>`. *AgentRelay, esfuerzo alto; la sesión revisa.* 0.8.0.
- [~] **A7. AppImage.** *(Archivos, CI y docs recuperados en 0.7.0, idénticos al original y con sintaxis comprobada; falta que el usuario lo construya y lo pruebe en su Debian)* Traer `packaging/linux/` de `35970a1`, adaptarlo y añadir el job `build-linux` al CI; el usuario lo prueba en su Debian. *AgentRelay, esfuerzo medio.* 0.8.x.

- [ ] **A8. Modo «Rápido» con la gráfica.** Perfil de codificación por hardware (HEVC/H.264 con NVENC, QSV, VAAPI o AMF, el primero que confirme `probe_hardware_encoders`), con calidad constante equivalente a cada nivel (`-cq`/`-global_quality`/`-qp` según el codificador). Solo se ofrece si hay uno que funciona; si la codificación falla, repite el vídeo con el perfil normal por CPU. Diseño del mapeo de calidad: sesión (Opus); implementación: AgentRelay, esfuerzo alto. 0.8.0.

## Fase B: rediseño (maqueta de Plegat aprobada)

- [x] **B1. Tokens ampliados y QSS.** *(Hecho en 0.7.1, AgentRelay, revisado; todos los contrastes ≥ 4,5:1. Nota para B2: la regla general `QWidget { background-color: bg }` pinta los contenedores; dentro de `#sideBar` hay que ponerlos transparentes o con `sidebar_bg`, sobre todo en Cinta)* `ThemeTokens` gana lo que la maqueta usa: radios por componente, grosor de borde, desplazamiento de sombra (Riso), colores de barra lateral, chips, segmentos, estados hover/pressed/disabled. QSS regenerado; tests de que los 6 juegos (3 temas × claro/oscuro) generan QSS válido y contrastes ≥ 4,5:1 en texto. *AgentRelay, esfuerzo alto; maqueta en references.*
- [ ] **B2. Estructura de ventana.** `MainWindow`: barra lateral (logo + `StepList` nueva + modo segmentado + Preferencias), contenido + columna «Tu vídeo», barra de transporte inferior (`TransportBar`, reemplaza `QueuePanel`; misma API de señales que hoy). Diseño compacto (< 900 px): la columna de contexto pasa debajo. *AgentRelay, esfuerzo xhigh.*
- [ ] **B3. Componentes.** `SegmentedControl`, `Chip`, `StatTile`, `OptionCard` nueva (radio + nombre + descripción + tamaño grande + barra, altura por contenido: corrige el recorte), `VideoRow` (delegado de lista con miniatura, chips 1080p/4K, estado y quitar), `Disclosure` para «Detalles técnicos». *AgentRelay, esfuerzo alto.*
- [ ] **B4. Pintores por tema.** `gui/theme/painters.py` con una interfaz común (`paint_selected_card`, `paint_title`, `paint_progress`, `paint_motif`): Plegat (esquina doblada, barra en acordeón, gato de origami), Riso (sombra desplazada, título con registro movido, tramado, gato tramado que se encoge), Cinta (franjas, contador mecánico, platina con bobinas). «Reducir animaciones» salta al estado final. *AgentRelay, esfuerzo xhigh; revisión visual de la sesión con capturas.*
- [ ] **B5. Pasos del asistente con la estructura nueva:** Vídeos, Dónde verlos, Calidad, Qué conservar, Destino, Resumen, Avanzado, Preferencias y la pantalla de FFmpeg ausente. Uno o dos pasos por tarea. *AgentRelay, esfuerzo alto.*
- [ ] **B6. Revisión visual y capturas.** Script de capturas de la ventana real (el de la sesión está en el scratchpad; convertirlo en `scripts/screenshots.py` usando `QWidget.grab()` con la plataforma nativa, no offscreen). Capturas nuevas en `docs/screenshots/`, docs ES/EN. *Sesión (Opus).* 0.9.0.

## Fase C: publicación

- [ ] **C1.** Revisar el instalador de Windows en un equipo limpio, AppImage en Debian, release 1.0.0 (con OK del usuario).

## Dudas abiertas

- ¿Pasar el perfil «archive» de `preset slow` a `medium`? En la medición sintética de este PC, `slow` tardó 2,2 veces más sin dar un archivo menor; falta medir con vídeo real antes de decidir. Cambia el comportamiento: lo decide el usuario.
- ¿Riso y Cinta tal como están en la maqueta, o hay que retocarlos? Pendiente de respuesta; no bloquea, porque se empieza por Plegat.
