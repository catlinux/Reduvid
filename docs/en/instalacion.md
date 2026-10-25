# Reduvid installers

[Castellano](../es/instalacion.md) · **English**

This guide explains how to build the Windows installer and the Linux AppImage from the source code. Neither of them includes FFmpeg: Reduvid uses the one installed on the system.

## Windows

The installer is built with PyInstaller in folder mode and Inno Setup.

### Requirements

- 64-bit Windows 10 or 11 to build and test the package.
- Python 3.11 or later.
- FFmpeg with `libx264` and `libx265`, on the `PATH` or configured in Reduvid.
- Inno Setup 6, only to build the installer.
- The repository cloned and a terminal open at its root.

### Build the package

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

   In `cmd.exe`, use `.venv\Scripts\activate.bat`.

2. Install the build dependencies:

   ```powershell
   python -m pip install -e ".[build]"
   ```

3. Generate the package folder:

   ```powershell
   python scripts/build_windows.py
   ```

The result is in `dist\windows\Reduvid\`: `Reduvid.exe` and the `_internal\` folder with Qt, the fonts and the translations. It is a folder package (`--onedir`), not a single executable; the whole folder must be distributed. FFmpeg is not copied into it.

### Build the installer

1. Download and install [Inno Setup](https://jrsoftware.org/isdl.php) with the default options.
2. Check that `ISCC.exe` is on the `PATH`. If the Inno Setup installer did not add it, open a new terminal or add its folder, usually `C:\Program Files (x86)\Inno Setup 6`.
3. Run the build again:

   ```powershell
   python scripts/build_windows.py
   ```

The script builds the package with PyInstaller first and then calls Inno Setup with the version read from `src\reduvid\__init__.py`; it does not have to be written by hand. The installer is written to `dist\windows\Reduvid-Setup-<version>.exe`.

If `ISCC.exe` is not available, the script finishes successfully after building the package and warns that it did not create the installer.

### What the installer does

- Installs Reduvid in `C:\Program Files\Reduvid`.
- Creates a **Reduvid** shortcut in the Start menu.
- Offers a desktop shortcut, unchecked by default.
- Adds an uninstaller in **Installed apps** that removes the installed files without touching the user's configuration or videos.
- Lets the user open Reduvid when installation finishes.
- Uses a fixed application identifier, so a new version upgrades the existing installation.

### SmartScreen warning

The installer is not digitally signed, so the first time Windows SmartScreen may show "Windows protected your PC". To continue, click **More info** and then **Run anyway**; there is no need to disable any Windows protection.

## Linux (AppImage)

The AppImage includes Python, Qt and Reduvid, so the application and its Python dependencies do not have to be installed. FFmpeg remains external: Reduvid looks for it on the system or at the configured path.

### Requirements

- Linux x86_64, targeting Debian 12 or later.
- Python 3.11 or later, `python3-venv`, `curl` and the PyInstaller tools (`ldd`, `objdump`, `objcopy`), only to build the AppImage.
- FFmpeg with `libx264` and `libx265`, to use the application.
- The usual Qt graphical libraries on the system (X11 or Wayland).
- FUSE only if the distribution cannot run AppImages without extracting them; if it is missing, `--appimage-extract-and-run` can be used.

### Build the AppImage

From the repository root:

```bash
bash packaging/linux/build_appimage.sh
```

The script creates an isolated Python environment, installs Reduvid and PyInstaller, bundles Python, Qt, the fonts and the translations, and downloads [appimagetool 1.9.1](https://github.com/AppImage/appimagetool/releases/tag/1.9.1) and the AppImage runtime 20251108 if they are not there yet. The result is `dist/linux/Reduvid-<version>-x86_64.AppImage`.

### Run the AppImage

From `dist/linux/`:

```bash
chmod +x Reduvid-<version>-x86_64.AppImage
./Reduvid-<version>-x86_64.AppImage
```

If the distribution does not have FUSE:

```bash
./Reduvid-<version>-x86_64.AppImage --appimage-extract-and-run
```

On startup, if it cannot find FFmpeg, Reduvid shows the screen with instructions to install it.
