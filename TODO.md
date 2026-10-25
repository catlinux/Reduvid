# Pendiente

**Castellano** · [English](TODO.en.md)

El plan detallado de cada paso está en [.agents/plans/reduvid/reduvid.PLAN.md](.agents/plans/reduvid/reduvid.PLAN.md).

## Prioridad alta

- Definir cómo se licencian las contribuciones externas de código antes de aceptar la primera: la licencia solo cubre material de Catlinux.
- Fase 4 (0.4.0 → 1.0.0), empaquetado: icono de la aplicación, instalador de Windows (PyInstaller + Inno Setup) y AppImage de Linux, probados en un Windows y un Debian reales con un vídeo de prueba de unos 6 GB.

## Prioridad media

- Al crear el repositorio en GitHub: descripción «About», topics (`video`, `ffmpeg`, `jellyfin`, `h264`, `h265`, `video-compression`, `pyside6`, `cross-platform`) y avisos privados de seguridad activados.
- `estimate_from_sample` (`core/estimate.py`) tiene el parámetro `original_sample_bytes` sin usar desde el paso 3.1; limpiar si se retoma ese módulo.

## Prioridad baja / más adelante

- AV1 (libsvtav1): la arquitectura de perfiles ya lo permite; falta perfil, pruebas y explicación.
- Aceleración por hardware (NVENC, QSV, VAAPI) pulida: en 0.1.0 solo se detecta e informa.
- Instalación sin Qt para servidores Linux (solo `reduvid-cli`): decidir en la Fase 4 cómo separar la dependencia de PySide6.
- Perfil de destino para la plataforma de reproducción propia del autor, cuando exista.
- OCR de subtítulos de imagen a texto (necesitaría Tesseract como herramienta externa).
- Paquetes .deb y Flatpak.
- macOS: no es objetivo ahora; no romperlo sin motivo.
- Más idiomas de la interfaz.
- `scripts/screenshots.py` para automatizar las capturas con Qt offscreen: en este equipo el backend offscreen no tiene fuentes registradas (0 familias) y el texto saldría vacío; las capturas de la 0.2.0 se hicieron a mano con la ventana real.

## Descartado

- **Incluir FFmpeg en el repositorio o en los paquetes:** por licencia (GPL de libx264/libx265) y por tamaño. Se usa el del sistema.
- **Tkinter:** no permite el diseño propio que busca el proyecto.
- **PySide6 completo (con Addons):** pesa mucho más y no hace falta; basta PySide6-Essentials.
- **Telemetría o comprobación de actualizaciones en línea:** el programa no se conecta a la red.
