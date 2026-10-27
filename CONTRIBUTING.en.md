# Contributing

[Castellano](CONTRIBUTING.md) · **English**

Thanks for your interest in Reduvid. Please open an issue before starting anything big so we can discuss it first.

## Licensing of contributions

Reduvid uses the [WNCL-CU-1.0](LICENSE) license, which covers material owned by Catlinux. Code contributions are accepted under the **[Developer Certificate of Origin (DCO) 1.1](https://developercertificate.org/)**: by signing off your commit (`git commit -s`) you certify that you have the right to submit that code and that you do so under the project's license. No other document needs to be signed and authorship is not transferred; the DCO only certifies the code's origin. Pull requests with unsigned commits cannot be merged.

## Setting up

```bash
git clone https://github.com/catlinux/Reduvid.git
cd Reduvid
# On Debian/Ubuntu the command is python3 (if it fails: sudo apt install python3-venv)
python3 -m venv .venv          # Windows: py -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
pre-commit install
```

Integration tests need FFmpeg with `libx264` and `libx265` on your `PATH`. Without it, those tests are skipped.

## Checks

All of these must pass before submitting changes:

```bash
ruff check .
ruff format --check .
mypy
pytest
python scripts/check_doc_sync.py
```

## Commits

We use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/), with the type in English and the description in Spanish:

```text
feat: añade perfil Jellyfin compatible
fix: no sobrescribe la salida si ya existe
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`, `style`, `perf`. The `main` branch is stable; work happens on `feat/…` or `fix/…` branches.

## Documentation in two languages

All documentation exists in Spanish and English:

- At the root, `X.md` (Spanish) and `X.en.md` (English).
- Under `docs/`, `docs/es/` and `docs/en/` with the same file names.

If you change a document, change its counterpart in the same commit. `scripts/check_doc_sync.py` checks that every pair exists and has the same heading structure; it runs in pre-commit and CI.

## Translating the interface

The application texts (interface and command line) are available in Català, Castellano and English, with gettext files (`.po`) under `src/reduvid/locale/<language>/LC_MESSAGES/reduvid.po`. `msgid` strings are written in English and `en` uses the `msgid` as is.

To update the translations:

```bash
python scripts/extract_translations.py   # extract new strings and update ca and es
python scripts/compile_translations.py   # compile the .po files to .mo for local testing
```

`extract_translations.py` writes `src/reduvid/locale/reduvid.pot` and updates the `ca` and `es` catalogs, keeping existing translations; then fill in the empty `msgstr` entries of the `.po` files. The `.mo` files are not committed: `pip install -e .` and the wheel build generate them with the hook in `hatch_build.py`. `pytest` checks that no entry is left untranslated and that the `.pot` file is up to date.

## Code guidelines

- Python ≥ 3.11 with full type hints.
- Every source file starts with:

  ```python
  # SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
  # Copyright (C) 2026 Catlinux
  ```
- External processes are always started with an argument list, never with `shell=True` or string concatenation.
- The engine (`src/reduvid/core/`) never imports Qt; the interface never builds FFmpeg commands.
- No telemetry and no network connections.
