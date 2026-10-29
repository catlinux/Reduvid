# Cómo contribuir

**Castellano** · [English](CONTRIBUTING.en.md)

Gracias por tu interés en Reduvid. Abre una *issue* antes de empezar algo grande, para hablarlo primero.

## Licencia de las contribuciones

Reduvid usa la licencia [WNCL-CU-1.0](LICENSE), que cubre el material de Catlinux. Las contribuciones de código se aceptan bajo el **[Developer Certificate of Origin (DCO) 1.1](https://developercertificate.org/)**: al firmar tu commit (`git commit -s`) certificas que tienes derecho a aportar ese código y que lo haces bajo la licencia del proyecto. No hace falta firmar ningún otro documento ni ceder la autoría; el DCO solo certifica el origen del código. Las *pull requests* sin commits firmados no se podrán fusionar.

## Preparar el entorno

```bash
git clone https://github.com/catlinux/Reduvid.git
cd Reduvid
# En Debian/Ubuntu el comando es python3 (si falla: sudo apt install python3-venv)
python3 -m venv .venv          # Windows: py -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
pre-commit install
```

Para los tests de integración necesitas FFmpeg con `libx264` y `libx265` en el `PATH`. Sin él, esos tests se saltan.

## Comprobaciones

Antes de enviar cambios deben pasar todas:

```bash
ruff check .
ruff format --check .
mypy
pytest
python scripts/check_doc_sync.py
```

## Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/), con el tipo en inglés y la descripción en castellano:

```text
feat: añade perfil Cinecat compatible
fix: no sobrescribe la salida si ya existe
```

Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`, `style`, `perf`. La rama `main` es estable; el trabajo va en ramas `feat/…` o `fix/…`.

## Documentación en dos idiomas

Toda la documentación existe en castellano e inglés:

- En la raíz, `X.md` (castellano) y `X.en.md` (inglés).
- En `docs/`, `docs/es/` y `docs/en/` con los mismos nombres de archivo.

Si cambias un documento, cambia su pareja en el mismo commit. `scripts/check_doc_sync.py` comprueba que cada pareja existe y tiene la misma estructura de títulos; se ejecuta en pre-commit y en CI.

## Traducir la interfaz

Los textos de la aplicación (interfaz y línea de órdenes) están en català, castellano e inglés, con gettext (`.po`) dentro de `src/reduvid/locale/<idioma>/LC_MESSAGES/reduvid.po`. Los `msgid` se escriben en inglés y `en` usa el `msgid` tal cual.

Para actualizar las traducciones:

```bash
python scripts/extract_translations.py   # extrae los textos nuevos y actualiza ca y es
python scripts/compile_translations.py   # compila los .po a .mo para probarlo en local
```

`extract_translations.py` escribe `src/reduvid/locale/reduvid.pot` y actualiza los catálogos de `ca` y `es` conservando lo ya traducido; después traduce los `msgstr` vacíos de los `.po`. Los `.mo` no se suben: los genera `pip install -e .` y la construcción del wheel mediante el hook de `hatch_build.py`. `pytest` comprueba que no queden entradas sin traducir ni que el `.pot` esté desfasado.

## Normas de código

- Python ≥ 3.11 con tipado completo.
- Cada archivo fuente empieza con:

  ```python
  # SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
  # Copyright (C) 2026 Catlinux
  ```
- Los procesos externos se lanzan siempre con una lista de argumentos, nunca con `shell=True` ni concatenando texto.
- El motor (`src/reduvid/core/`) no importa Qt; la interfaz no construye órdenes de FFmpeg.
- Nada de telemetría. La única conexión de red es la comprobación de actualizaciones, que se puede desactivar (ver [Privacidad](README.md#privacidad)).
