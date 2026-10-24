@AGENTS.md

# Reduvid — instrucciones del proyecto

Compresor de vídeo con interfaz gráfica (Linux y Windows) para que cualquiera reduzca sus vídeos perdiendo muy poca calidad, pensado para bibliotecas Jellyfin. Usa FFmpeg como herramienta externa y lo oculta tras un asistente paso a paso. Autor y titular: **Catlinux** (`https://github.com/catlinux`). Repo: `git@github-catlinux:catlinux/Reduvid.git`.

Hoja de ruta y estado de cada paso: [.agents/plans/reduvid/reduvid.PLAN.md](.agents/plans/reduvid/reduvid.PLAN.md). Léela antes de empezar cualquier tarea.

## Forma de trabajar

- Por fases (ver el plan). Al terminar una fase: resume qué hay, cómo probarlo y qué viene, y **espera el visto bueno** antes de seguir.
- Decide lo trivial y anótalo en el plan. Pregunta ante lo importante, irreversible o de gusto personal: nombre, diseño, licencia, dependencias nuevas, cambios de comportamiento hacia el usuario.
- Nunca push, release, tag ni repo remoto sin OK explícito.
- Sin sobreingeniería: primero sólido; lo ambicioso va a `TODO.md`.

## Decisiones tomadas

- **Licencia:** WNCL-CU-1.0 (`LicenseRef-WNCL-CU-1.0`) solo para el material propio; los terceros conservan la suya (ver `THIRD_PARTY_NOTICES.md`). Cambios de licencia, solo con la Skill `licencias` y autorización.
- **Lenguaje:** Python ≥ 3.11 (CI con 3.11 y 3.13). Build con hatchling. La versión vive **solo** en `src/reduvid/__init__.py` (`__version__`).
- **Interfaz:** PySide6-Essentials (solo QtCore/QtGui/QtWidgets, sin Addons, para no pesar) con estilo propio por QSS generado desde tokens de tema. Se permite cambiar entre varios temas.
- **Dependencias de ejecución:** PySide6-Essentials (LGPL-3), platformdirs (MIT), Send2Trash (BSD-3), psutil (BSD-3). Añadir otra requiere preguntar.
- **Traducción:** gettext (dominio `reduvid`, `.po` en `src/reduvid/locale/`), compartido por la CLI y la interfaz; Babel solo en desarrollo. Idiomas: ca, es, en.
- **FFmpeg:** nunca dentro del repo ni de los paquetes. Se detecta en la ruta configurada y luego en el PATH.
- **Destinos («¿dónde lo vas a ver?»)** como perfiles de datos, no como código especial: añadir el reproductor propio del autor en el futuro debe ser un perfil más.

## Arquitectura

- `src/reduvid/core/`: motor sin dependencias de Qt (detección de FFmpeg, ffprobe, perfiles, plan de codificación, construcción de comandos, ejecución, verificación, cola). Todo lo testeable vive aquí.
- `src/reduvid/cli.py`: CLI sobre el mismo motor.
- `src/reduvid/gui/`: interfaz; solo presenta y llama al motor.
- La interfaz nunca construye comandos de FFmpeg; el motor nunca importa Qt.

## Convenciones de código

- Tipado completo (mypy estricto en `core/`), ruff para lint y formato, longitud de línea 100.
- Cabecera en cada fuente:
  ```python
  # SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
  # Copyright (C) 2026 Catlinux
  ```
- Seguridad: procesos siempre con lista de argumentos, nunca `shell=True` ni texto concatenado. Las rutas se pasan absolutas (`Path.resolve()`), así ningún nombre puede empezar por `-` y confundirse con una opción.
- Rutas con `pathlib`; directorios de usuario con `platformdirs`. Cuidado con espacios, tildes y Unicode (hay tests).
- Los originales no se tocan nunca por defecto. Se escribe a un temporal en la carpeta de destino y solo se renombra tras verificar. Nunca se sobrescribe.
- Sin telemetría ni conexiones de red.
- Comentarios solo para el porqué no obvio; en el perfil Jellyfin, cada valor lleva su porqué.
- Textos de la interfaz siempre por gettext (`_()`); sin jerga sin explicar.

## Tests

```bash
python -m pip install -e ".[dev]"
pytest                 # los tests que necesitan FFmpeg se saltan si no está instalado
ruff check . && ruff format --check . && mypy
pre-commit run --all-files
python scripts/check_doc_sync.py
```

Los vídeos de prueba se generan con FFmpeg en `tests/_media/` (ignorado); nunca se suben binarios.

## Git

- Conventional Commits: tipo en inglés y descripción en castellano (`feat: añade perfil Jellyfin compatible`). Tipos: feat, fix, docs, refactor, test, build, ci, chore, style, perf.
- `main` estable y ramas `feat/…` o `fix/…` por funcionalidad. Crear ramas sigue necesitando el OK del usuario.
- Cada trabajo acabado sube la versión y lleva su entrada en `CHANGELOG.md` **y** `CHANGELOG.en.md`, en el mismo commit.

## Bilingüismo

- Documentación en castellano (`X.md`) e inglés (`X.en.md`, o `docs/en/`), siempre sincronizadas en el mismo commit. `scripts/check_doc_sync.py` comprueba que cada pareja exista y tenga la misma estructura de títulos; corre en CI.
- Commits en castellano. Interfaz en ca/es/en.
