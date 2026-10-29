# Actualizaciones automáticas

Estado: `[x]` hecho · `[ ]` pendiente · `[~]` en curso. El ejecutor marca cada paso. Ante un imprevisto de diseño, **para** y anótalo en «Dudas abiertas».

## Decisiones del usuario (2026-10-27)

- **Activadas por defecto, con aviso:** al primer arranque se explica qué hace y se puede desactivar en Preferencias. Sustituye a la regla anterior «sin conexiones de red».
- **Descargar e instalar:** no solo avisar.

## Diseño (sesión, Opus)

- **Fuente:** las *releases* públicas de GitHub: `GET https://api.github.com/repos/catlinux/Reduvid/releases/latest`, sin autenticación. Solo se envía la petición con `User-Agent: Reduvid/<versión>`: ni identificadores ni datos de uso. Se ignoran borradores y *prereleases*.
- **Frecuencia:** como máximo una vez cada 24 h, al arrancar y en segundo plano. La hora de la última comprobación va en un archivo de estado en la caché del usuario (`platformdirs.user_cache_dir`), no en la configuración. Sin red, o con error, falla en silencio.
- **HTTP:** `urllib.request` de la biblioteca estándar, con TLS por defecto y tiempo límite de 10 s. Sin dependencias nuevas.
- **Versiones:** SemVer `x.y.z` desde el `tag_name` `vX.Y.Z`; solo se actualiza a una versión mayor que `__version__`.
- **Archivos de cada release:** `Reduvid-Setup-X.Y.Z.exe`, `Reduvid-X.Y.Z-x86_64.AppImage` y `SHA256SUMS`, el formato de `sha256sum`. La descarga se comprueba contra `SHA256SUMS` y, si no coincide, se borra y no se instala. Esto protege de descargas corruptas o cortadas, no de una cuenta de GitHub comprometida: no hay firma de código; queda anotado en «Dudas abiertas».
- **Qué se hace según la instalación:**
  - Windows con el instalador (`sys.frozen` y ejecutable bajo la carpeta de instalación): descarga el instalador a la caché y lo verifica. Ofrece «Instalar ahora» o «Al cerrar». Lo lanza separado del proceso con `/SILENT /SUPPRESSMSGBOXES /NORESTART` y cierra Reduvid. El instalador usa el mismo `AppId`, así que actualiza encima.
  - Linux AppImage (variable de entorno `APPIMAGE`): descarga junto al AppImage actual con nombre temporal, verifica, pone permisos de ejecución, reemplaza de forma atómica (`os.replace`) y ofrece reiniciar.
  - Desde el código fuente o pip: solo avisa y enlaza a la página de la release.
- **Nunca** durante una conversión: si hay una en marcha, el aviso espera a que termine.
- **Instalador de Windows por usuario:** se pasa a `PrivilegesRequired=lowest` e instalación en `{localappdata}\Programs\Reduvid`, para que la actualización no pida permisos de administrador (UAC) cada vez. Es lo habitual (VS Code, Discord). La 0.8.0 instalada en `Program Files` habrá que desinstalarla una vez a mano; queda dicho en las notas de la release.
- Motor en `core/updates.py`, sin Qt; interfaz en `gui/update_notice.py` y Preferencias.

## Pasos

- [x] **U1. Releases en el CI.** *(Hecho, AgentRelay, revisado: `release.yml` con verificación de tag/versión/CHANGELOG, `scripts/release_notes.py`, instalador por usuario. Sin probar en GitHub hasta el tag de U5)* Workflow que, al subir un tag `vX.Y.Z`, construye el instalador de Windows y el AppImage, genera `SHA256SUMS` y crea la release de GitHub con los tres archivos y las notas de esa versión del `CHANGELOG.md` (con `gh release create` y `GITHUB_TOKEN`). Instalador por usuario (`packaging/windows/reduvid.iss`). Crear tags sigue necesitando el OK del usuario cada vez. *AgentRelay, esfuerzo alto.*
- [x] **U2. Motor `core/updates.py`.** *(Hecho, AgentRelay, revisado; la sesión hizo que solo una respuesta correcta inicie la espera de 24 h y que se ignoren los assets que no sean HTTPS)* `check_for_update(current, *, now, state_dir, opener) -> UpdateInfo | None` (24 h, ignora borradores y prereleases, compara SemVer); `download_update(info, kind, dest_dir, *, progress, cancel) -> Path` con verificación SHA256; `install_kind() -> Literal["windows_installer", "appimage", "source"]`; `launch_windows_installer(path)` y `replace_appimage(new, current)`. Tests sin red: `opener` falso y `tmp_path`. *AgentRelay, esfuerzo alto.*
- [x] **U3. Interfaz.** *(Hecho, AgentRelay, revisado: `gui/update_notice.py`, workers de comprobación y descarga, casilla en Preferencias, aviso del primer arranque. Pendiente de pulir: las notas se muestran con el Markdown en crudo. Sin probar contra una release real hasta U5)* `Config.check_updates: bool = True`; casilla en Preferencias; aviso del primer arranque, una sola vez, con el texto de qué se envía; aviso no intrusivo cuando hay versión nueva, con lo que cambia, «Instalar ahora», «Al cerrar» y «Ahora no»; descarga con progreso y cancelable; espera si hay una conversión en marcha. Traducciones ca/es. *AgentRelay, esfuerzo alto.*
- [ ] **U4. Documentación y regla.** README «Privacidad» (ES/EN) explicando la única conexión, `gui.md`, `CLAUDE.md` (ya cambiado por la sesión) y TODO. *AgentRelay, esfuerzo medio.* Versión 0.9.0 (menor).
- [ ] **U5. Primera release con el OK del usuario:** tag `v0.9.0`, comprobar que la release tiene los tres archivos, y probar la actualización de 0.9.0 → 0.9.1 en Windows y AppImage.

## Dudas abiertas

- Sin firma de código, la integridad depende de la cuenta de GitHub. Firmar el instalador (certificado de Windows, de pago) o firmar `SHA256SUMS` con una clave propia (minisign) queda para más adelante, si el usuario lo quiere.
