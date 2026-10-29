# Instaladores de Reduvid

**Castellano** · [English](../en/instalacion.md)

Esta guía explica cómo generar el instalador de Windows y el AppImage de Linux a partir del código fuente. Ninguno de los dos incluye FFmpeg: Reduvid usa el que haya instalado en el sistema.

## Windows

El instalador se genera con PyInstaller en modo carpeta e Inno Setup.

### Requisitos

- Windows 10 u 11 de 64 bits para generar y probar el paquete.
- Python 3.11 o posterior.
- FFmpeg con `libx264` y `libx265`, disponible en el `PATH` o configurado en Reduvid.
- Inno Setup 6, solo si quieres generar el instalador.
- El repositorio clonado y una consola abierta en su raíz.

### Compilar el paquete

1. Crea y activa un entorno virtual:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

   En `cmd.exe`, usa `.venv\Scripts\activate.bat`.

2. Instala las dependencias de compilación:

   ```powershell
   python -m pip install -e ".[build]"
   ```

3. Genera la carpeta del paquete:

   ```powershell
   python scripts/build_windows.py
   ```

El resultado queda en `dist\windows\Reduvid\`: `Reduvid.exe` y la carpeta `_internal\` con Qt, las fuentes y las traducciones. Es un paquete de carpeta (`--onedir`), no un único ejecutable; hay que distribuir la carpeta completa. FFmpeg no se copia dentro.

### Generar el instalador

1. Descarga e instala [Inno Setup](https://jrsoftware.org/isdl.php) con las opciones predeterminadas.
2. Comprueba que `ISCC.exe` está en el `PATH`. Si el instalador de Inno Setup no lo añadió, abre una consola nueva o añade su carpeta, normalmente `C:\Program Files (x86)\Inno Setup 6`.
3. Ejecuta otra vez:

   ```powershell
   python scripts/build_windows.py
   ```

El script compila primero el paquete con PyInstaller y después llama a Inno Setup con la versión leída de `src\reduvid\__init__.py`; no hay que escribirla a mano. El instalador queda en `dist\windows\Reduvid-Setup-<versión>.exe`.

Si `ISCC.exe` no está disponible, el script termina correctamente tras generar el paquete y avisa de que no ha creado el instalador.

### Qué hace el instalador

- Instala Reduvid en tu carpeta de usuario, por defecto `C:\Users\<usuario>\AppData\Local\Programs\Reduvid`, sin pedir permisos de administrador.
- Crea un acceso directo **Reduvid** en el menú Inicio.
- Ofrece un acceso directo en el escritorio, desmarcado por defecto.
- Añade un desinstalador en **Aplicaciones instaladas** que borra los archivos instalados, sin tocar la configuración ni los vídeos del usuario.
- Permite abrir Reduvid al terminar la instalación.
- Usa un identificador de aplicación fijo, de modo que una versión nueva actualiza la instalación existente.

### Aviso de SmartScreen

El instalador no está firmado digitalmente, así que la primera vez Windows SmartScreen puede mostrar «Windows protegió su PC». Para continuar, pulsa **Más información** y después **Ejecutar de todas formas**; no hace falta desactivar ninguna protección de Windows.

## Linux (AppImage)

El AppImage incluye Python, Qt y Reduvid, así que no hay que instalar la aplicación ni sus dependencias de Python. FFmpeg sigue siendo externo: Reduvid lo busca en el sistema o en la ruta configurada.

### Requisitos

- Linux x86_64, pensado para Debian 12 o posterior.
- Python 3.11 o posterior, `python3-venv`, `curl` y las herramientas de PyInstaller (`ldd`, `objdump`, `objcopy`), solo para construir el AppImage.
- FFmpeg con `libx264` y `libx265`, para usar la aplicación.
- Las bibliotecas gráficas habituales de Qt en el sistema (X11 o Wayland).
- FUSE solo si la distribución no permite ejecutar AppImages sin extraerlos; si falta, se puede usar `--appimage-extract-and-run`.

### Construir el AppImage

Desde la raíz del repositorio:

```bash
bash packaging/linux/build_appimage.sh
```

El script crea un entorno Python aislado, instala Reduvid y PyInstaller, empaqueta Python, Qt, las fuentes y las traducciones, y descarga [appimagetool 1.9.1](https://github.com/AppImage/appimagetool/releases/tag/1.9.1) y el runtime de AppImage 20251108 si aún no están. El resultado es `dist/linux/Reduvid-<versión>-x86_64.AppImage`.

### Ejecutar el AppImage

Desde `dist/linux/`:

```bash
chmod +x Reduvid-<versión>-x86_64.AppImage
./Reduvid-<versión>-x86_64.AppImage
```

Si la distribución no tiene FUSE:

```bash
./Reduvid-<versión>-x86_64.AppImage --appimage-extract-and-run
```

Al abrirse, si no encuentra FFmpeg, Reduvid muestra la pantalla con instrucciones para instalarlo.
