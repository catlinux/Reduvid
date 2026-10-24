# Avisos de terceros · Third-party notices

[Castellano](#castellano) · [English](#english)

## Castellano

La licencia de Reduvid (WNCL-CU-1.0) solo cubre el material de Catlinux. Cada componente de terceros conserva su propia licencia y sus avisos. El repositorio no incluye material de terceros. Las licencias de esta tabla se han comprobado en los metadatos de cada paquete (24-10-2026).

### Dependencias de ejecución

Se instalan aparte con pip y, a partir de la 0.4.0, se incluirán en los paquetes de Windows y Linux.

| Componente | Licencia | Enlace | Notas |
| --- | --- | --- | --- |
| PySide6-Essentials y shiboken6 (Qt for Python) | LGPL-3.0-only (o GPL-2.0/3.0) | https://pyside.org | Se usa bajo LGPL-3.0 |
| platformdirs | MIT | https://github.com/tox-dev/platformdirs | |
| Send2Trash | BSD-3-Clause | https://github.com/arsenetar/send2trash | |
| psutil | BSD-3-Clause | https://github.com/giampaolo/psutil | |

**Compatibilidad con la LGPL-3.0 (Qt/PySide6).** Reduvid usa Qt como biblioteca enlazada dinámicamente y sin modificarla. Los paquetes que la incluyan deben:

1. Mantener Qt/PySide6 como bibliotecas separadas y sustituibles. En Windows se usará PyInstaller en modo carpeta, no un ejecutable único.
2. Incluir el texto de la LGPL-3.0 y de la GPL-3.0 e indicar dónde obtener el código fuente de esa versión de Qt/PySide6.
3. No prohibir la ingeniería inversa necesaria para depurar modificaciones de Qt.

Las restricciones de cobro de WNCL-CU-1.0 se aplican al material de Reduvid, no a Qt. Se revisará de nuevo antes de la primera release.

### Herramientas de desarrollo

No se distribuyen con Reduvid.

| Componente | Licencia |
| --- | --- |
| pytest | MIT |
| ruff | MIT |
| mypy | MIT |
| pre-commit | MIT |
| Babel | BSD-3-Clause |

### FFmpeg

Reduvid **no incluye ni distribuye FFmpeg**: lo ejecuta como programa externo instalado por el usuario. Su licencia (LGPL o GPL, según la compilación) rige FFmpeg y no Reduvid.

### Tipografías e iconos

Ninguno todavía. Llegarán con la interfaz (0.2.0) y se documentarán aquí, cada uno con su archivo de licencia.

## English

Reduvid's license (WNCL-CU-1.0) only covers material owned by Catlinux. Each third-party component keeps its own license and notices. The repository contains no third-party material. The licenses below were checked against each package's metadata (2026-10-24).

### Runtime dependencies

Installed separately with pip and, from 0.4.0 on, bundled in the Windows and Linux packages.

| Component | License | Link | Notes |
| --- | --- | --- | --- |
| PySide6-Essentials and shiboken6 (Qt for Python) | LGPL-3.0-only (or GPL-2.0/3.0) | https://pyside.org | Used under LGPL-3.0 |
| platformdirs | MIT | https://github.com/tox-dev/platformdirs | |
| Send2Trash | BSD-3-Clause | https://github.com/arsenetar/send2trash | |
| psutil | BSD-3-Clause | https://github.com/giampaolo/psutil | |

**LGPL-3.0 compatibility (Qt/PySide6).** Reduvid uses Qt as an unmodified, dynamically linked library. Packages that bundle it must:

1. Keep Qt/PySide6 as separate, replaceable libraries. On Windows, PyInstaller will be used in folder mode, not as a single executable.
2. Include the LGPL-3.0 and GPL-3.0 texts and state where to get the source code of that Qt/PySide6 version.
3. Not prohibit the reverse engineering needed to debug modifications of Qt.

WNCL-CU-1.0's no-charge restrictions apply to Reduvid's material, not to Qt. This will be reviewed again before the first release.

### Development tools

Not distributed with Reduvid.

| Component | License |
| --- | --- |
| pytest | MIT |
| ruff | MIT |
| mypy | MIT |
| pre-commit | MIT |
| Babel | BSD-3-Clause |

### FFmpeg

Reduvid **does not include or distribute FFmpeg**: it runs it as an external program installed by the user. Its license (LGPL or GPL, depending on the build) governs FFmpeg, not Reduvid.

### Fonts and icons

None yet. They will arrive with the interface (0.2.0) and be documented here, each with its license file.
