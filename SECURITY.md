# Seguridad · Security

[Castellano](#castellano) · [English](#english)

## Castellano

### Versiones con soporte

Solo la última versión publicada recibe correcciones de seguridad.

### Cómo avisar de una vulnerabilidad

No abras una *issue* pública. Usa el aviso privado de GitHub: pestaña **Security** del repositorio → **Report a vulnerability**. Indica la versión, el sistema, los pasos para reproducirlo y su posible impacto. Recibirás respuesta lo antes posible.

### Alcance

Reduvid ejecuta FFmpeg sobre archivos que tú eliges. Interesan especialmente:

- Ejecución de órdenes a través de nombres de archivo o metadatos manipulados.
- Pérdida o sobrescritura de archivos originales.
- Cualquier conexión de red inesperada: la única conexión prevista es la comprobación de actualizaciones.

Las vulnerabilidades de FFmpeg se comunican a [FFmpeg](https://ffmpeg.org/security.html).

## English

### Supported versions

Only the latest released version receives security fixes.

### Reporting a vulnerability

Please do not open a public issue. Use GitHub's private reporting: the repository's **Security** tab → **Report a vulnerability**. Include the version, operating system, steps to reproduce and possible impact. You will get a reply as soon as possible.

### Scope

Reduvid runs FFmpeg on files you choose. Of particular interest:

- Command execution through crafted file names or metadata.
- Loss or overwriting of original files.
- Any unexpected network connection: the only expected one is the update check.

FFmpeg vulnerabilities should be reported to [FFmpeg](https://ffmpeg.org/security.html).
