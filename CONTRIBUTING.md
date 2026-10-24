# Cómo contribuir

**Castellano** · [English](CONTRIBUTING.en.md)

Gracias por tu interés en Reduvid. Abre una *issue* antes de empezar algo grande, para hablarlo primero.

## Licencia de las contribuciones

Reduvid usa la licencia [WNCL-CU-1.0](LICENSE), que cubre el material de Catlinux. Las contribuciones de código se aceptan bajo el **[Developer Certificate of Origin (DCO) 1.1](https://developercertificate.org/)**: al firmar tu commit (`git commit -s`) certificas que tienes derecho a aportar ese código y que lo haces bajo la licencia del proyecto. No hace falta firmar ningún otro documento ni ceder la autoría; el DCO solo certifica el origen del código. Las *pull requests* sin commits firmados no se podrán fusionar.

## Preparar el entorno

```bash
git clone https://github.com/catlinux/Reduvid.git
cd Reduvid
python -m venv .venv
# Linux: source .venv/bin/activate    Windows: .venv\Scripts\activate
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
feat: añade perfil Jellyfin compatible
fix: no sobrescribe la salida si ya existe
```

Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`, `style`, `perf`. La rama `main` es estable; el trabajo va en ramas `feat/…` o `fix/…`.

## Documentación en dos idiomas

Toda la documentación existe en castellano e inglés:

- En la raíz, `X.md` (castellano) y `X.en.md` (inglés).
- En `docs/`, `docs/es/` y `docs/en/` con los mismos nombres de archivo.

Si cambias un documento, cambia su pareja en el mismo commit. `scripts/check_doc_sync.py` comprueba que cada pareja existe y tiene la misma estructura de títulos; se ejecuta en pre-commit y en CI.

## Traducir la interfaz

La interfaz estará en català, castellano e inglés, con textos en archivos gettext (`.po`) dentro de `src/reduvid/locale/<idioma>/LC_MESSAGES/reduvid.po`. Esta sección explicará cómo añadir un idioma cuando la interfaz exista (versión 0.2.0).

## Normas de código

- Python ≥ 3.11 con tipado completo.
- Cada archivo fuente empieza con:

  ```python
  # SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
  # Copyright (C) 2026 Catlinux
  ```
- Los procesos externos se lanzan siempre con una lista de argumentos, nunca con `shell=True` ni concatenando texto.
- El motor (`src/reduvid/core/`) no importa Qt; la interfaz no construye órdenes de FFmpeg.
- Nada de telemetría ni conexiones de red.
