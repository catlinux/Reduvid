# Avisos de terceros · Third-party notices

[Castellano](#castellano) · [English](#english)

## Castellano

La licencia de Reduvid (WNCL-CU-1.0) solo cubre el material de Catlinux. Cada componente de terceros conserva su propia licencia y sus avisos. El repositorio incluye únicamente las tipografías de la sección «Tipografías e iconos». Las licencias de esta tabla se han comprobado en los metadatos de cada paquete (24-10-2026).

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

Se incluyen en `src/reduvid/resources/fonts/`, descargadas del repositorio `google/fonts` (`ofl/`), sin modificar y cada una con su `OFL.txt`. Se distribuyen con Reduvid bajo la SIL Open Font License 1.1, que permite redistribuirlas con el software siempre que se conserven el aviso de copyright y la licencia, y que no se vendan por separado. Los nombres de las fuentes no se usan para versiones modificadas. Iconos: ninguno todavía.

| Familia | Copyright | Origen | Licencia |
| --- | --- | --- | --- |
| Bricolage Grotesque | 2022 The Bricolage Grotesque Project Authors | https://github.com/ateliertriay/bricolage | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/bricolage-grotesque/OFL.txt)) |
| Instrument Sans | 2022 The Instrument Sans Project Authors | https://github.com/Instrument/instrument-sans | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/instrument-sans/OFL.txt)) |
| Archivo | 2020 The Archivo Project Authors | https://github.com/Omnibus-Type/Archivo | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/archivo/OFL.txt)) |
| Atkinson Hyperlegible | 2020 Braille Institute of America, Inc. | https://github.com/googlefonts/atkinson-hyperlegible | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/atkinson-hyperlegible/OFL.txt)) |
| Barlow | 2017 The Barlow Project Authors | https://github.com/jpt/barlow | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/barlow/OFL.txt)) |
| Barlow Condensed | 2017 The Barlow Project Authors | https://github.com/jpt/barlow | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/barlow-condensed/OFL.txt)) |
| JetBrains Mono | 2020 The JetBrains Mono Project Authors | https://github.com/JetBrains/JetBrainsMono | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/jetbrains-mono/OFL.txt)) |

## English

Reduvid's license (WNCL-CU-1.0) only covers material owned by Catlinux. Each third-party component keeps its own license and notices. The repository includes only the fonts listed under “Fonts and icons”. The licenses below were checked against each package's metadata (2026-10-24).

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

Included in `src/reduvid/resources/fonts/`, downloaded unmodified from the `google/fonts` repository (`ofl/`), each with its `OFL.txt`. They ship with Reduvid under the SIL Open Font License 1.1, which allows bundling them with software as long as the copyright notice and license are kept and they are not sold on their own. Font names are not used for modified versions. Icons: none yet.

| Family | Copyright | Source | License |
| --- | --- | --- | --- |
| Bricolage Grotesque | 2022 The Bricolage Grotesque Project Authors | https://github.com/ateliertriay/bricolage | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/bricolage-grotesque/OFL.txt)) |
| Instrument Sans | 2022 The Instrument Sans Project Authors | https://github.com/Instrument/instrument-sans | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/instrument-sans/OFL.txt)) |
| Archivo | 2020 The Archivo Project Authors | https://github.com/Omnibus-Type/Archivo | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/archivo/OFL.txt)) |
| Atkinson Hyperlegible | 2020 Braille Institute of America, Inc. | https://github.com/googlefonts/atkinson-hyperlegible | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/atkinson-hyperlegible/OFL.txt)) |
| Barlow | 2017 The Barlow Project Authors | https://github.com/jpt/barlow | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/barlow/OFL.txt)) |
| Barlow Condensed | 2017 The Barlow Project Authors | https://github.com/jpt/barlow | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/barlow-condensed/OFL.txt)) |
| JetBrains Mono | 2020 The JetBrains Mono Project Authors | https://github.com/JetBrains/JetBrainsMono | SIL OFL 1.1 ([texto](src/reduvid/resources/fonts/jetbrains-mono/OFL.txt)) |
