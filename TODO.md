# Pendiente

**Castellano** · [English](TODO.en.md)

El plan detallado de cada paso está en [.agents/plans/reduvid/reduvid.PLAN.md](.agents/plans/reduvid/reduvid.PLAN.md).

## Prioridad alta

- Definir cómo se licencian las contribuciones externas de código antes de aceptar la primera: la licencia solo cubre material de Catlinux.
- 0.7.0 → 0.9.0: decodificar con la gráfica si la hay, miniaturas, informe final, perfiles guardados, avisos tempranos de HDR, 10 bits y subtítulos de imagen, y el rediseño visual de los tres temas. Pasos en [.agents/plans/rediseno/rediseno.PLAN.md](.agents/plans/rediseno/rediseno.PLAN.md).

## Prioridad media

- 0.7.0 → 1.0.0: pipx, AppImage, probar el instalador de Windows en un equipo limpio, capturas y primera release.
- Al crear el repositorio en GitHub: descripción «About», topics (`video`, `ffmpeg`, `cinecat`, `h264`, `h265`, `video-compression`, `pyside6`, `cross-platform`) y avisos privados de seguridad activados.

## Prioridad baja / más adelante

- Comparación de fotograma antes/después en la prueba de muestra.
- Medir el margen de error real de la estimación (comparar con la conversión completa) antes de afirmar una cifra en la documentación.
- AV1 (libsvtav1): la arquitectura de perfiles ya lo permite; falta perfil, pruebas y explicación.
- Aceleración por hardware (NVENC, QSV, VAAPI) pulida: en 0.1.0 solo se detecta e informa.
- Instalación sin Qt para servidores Linux (solo `reduvid-cli`): decidir en la Fase 4 cómo separar la dependencia de PySide6.
- Firmar `SHA256SUMS` con una clave propia (minisign) o firmar el instalador, porque hoy no hay firma de código; Windows SmartScreen puede avisar de «editor desconocido».
- OCR de subtítulos de imagen a texto (necesitaría Tesseract como herramienta externa).
- Paquetes .deb y Flatpak.
- macOS: no es objetivo ahora; no romperlo sin motivo.
- Más idiomas de la interfaz.
- `scripts/screenshots.py` para automatizar las capturas con Qt offscreen: en este equipo el backend offscreen no tiene fuentes registradas (0 familias) y el texto saldría vacío; las capturas de la 0.2.0 se hicieron a mano con la ventana real.

## Descartado

- **Incluir FFmpeg en el repositorio o en los paquetes:** por licencia (GPL de libx264/libx265) y por tamaño. Se usa el del sistema.
- **Tkinter:** no permite el diseño propio que busca el proyecto.
- **PySide6 completo (con Addons):** pesa mucho más y no hace falta; basta PySide6-Essentials.
- **Telemetría:** el programa no envía datos de uso. La única conexión es la comprobación de actualizaciones (ver [Privacidad](README.md#privacidad)).
