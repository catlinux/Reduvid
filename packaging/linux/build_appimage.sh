#!/bin/bash
# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="$ROOT/build/linux"
APPDIR="$BUILD_DIR/AppDir"
DIST_DIR="$ROOT/dist/linux"
TOOLS_DIR="$BUILD_DIR/tools"
VENV="$BUILD_DIR/venv"
PYINSTALLER_DIR="$BUILD_DIR/pyinstaller"
APPIMAGETOOL_VERSION="1.9.1"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-x86_64.AppImage"
APPIMAGETOOL="$TOOLS_DIR/appimagetool-${APPIMAGETOOL_VERSION}-x86_64.AppImage"
RUNTIME_VERSION="20251108"
RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/${RUNTIME_VERSION}/runtime-x86_64"
RUNTIME="$TOOLS_DIR/runtime-x86_64-${RUNTIME_VERSION}"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "This script builds the Linux AppImage and must run on Linux." >&2
    exit 1
fi

if [[ "$(uname -m)" != "x86_64" ]]; then
    echo "This script currently builds x86_64 AppImages only." >&2
    exit 1
fi

for tool in python3 curl ldd objdump objcopy; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Required command not found: $tool" >&2
        exit 1
    fi
done

VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$ROOT/src/reduvid/__init__.py")"
if [[ -z "$VERSION" ]]; then
    echo "Could not read __version__ from src/reduvid/__init__.py" >&2
    exit 1
fi

rm -rf "$APPDIR" "$VENV" "$PYINSTALLER_DIR"
mkdir -p "$APPDIR/usr/lib" "$DIST_DIR" "$TOOLS_DIR" "$PYINSTALLER_DIR"

python3 -m venv "$VENV"
(
    cd "$ROOT"
    "$VENV/bin/python" -m pip install --no-cache-dir ".[build]"
)
"$VENV/bin/python" "$ROOT/scripts/compile_translations.py"

"$VENV/bin/python" -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --windowed \
    --name Reduvid \
    --distpath "$APPDIR/usr/lib" \
    --workpath "$PYINSTALLER_DIR" \
    --specpath "$PYINSTALLER_DIR" \
    --paths "$ROOT/src" \
    --add-data "$ROOT/src/reduvid/resources:reduvid/resources" \
    --add-data "$ROOT/src/reduvid/locale:reduvid/locale" \
    --exclude-module pytest \
    --exclude-module mypy \
    --exclude-module ruff \
    --exclude-module babel \
    --exclude-module pre_commit \
    "$ROOT/src/reduvid/__main__.py"

BUNDLE="$APPDIR/usr/lib/Reduvid"
APP_BINARY="$BUNDLE/Reduvid"
if [[ ! -x "$APP_BINARY" ]]; then
    echo "PyInstaller did not create $APP_BINARY" >&2
    exit 1
fi

for data in resources locale; do
    if [[ ! -d "$BUNDLE/_internal/reduvid/$data" ]]; then
        echo "PyInstaller did not bundle reduvid/$data" >&2
        exit 1
    fi
done

install -m 0755 "$ROOT/packaging/linux/AppDir/AppRun" "$APPDIR/AppRun"
install -m 0644 "$ROOT/packaging/linux/AppDir/reduvid.desktop" "$APPDIR/reduvid.desktop"
install -m 0644 "$ROOT/src/reduvid/resources/icon/reduvid.png" "$APPDIR/reduvid.png"

if [[ ! -x "$APPIMAGETOOL" ]]; then
    curl --fail --location --retry 3 --output "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
    chmod 0755 "$APPIMAGETOOL"
fi

if [[ ! -s "$RUNTIME" ]]; then
    curl --fail --location --retry 3 --output "$RUNTIME" "$RUNTIME_URL"
fi

OUTPUT="$DIST_DIR/Reduvid-${VERSION}-x86_64.AppImage"
rm -f "$OUTPUT"
ARCH=x86_64 VERSION="$VERSION" APPIMAGE_EXTRACT_AND_RUN=1 \
    "$APPIMAGETOOL" --no-appstream --runtime-file "$RUNTIME" "$APPDIR" "$OUTPUT"
chmod 0755 "$OUTPUT"
echo "AppImage: $OUTPUT"
