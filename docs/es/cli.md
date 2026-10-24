# Uso de la línea de órdenes

**Castellano** · [English](../en/cli.md)

`reduvid` tiene dos órdenes: `probe` (ver qué contiene un vídeo) y `convert` (reducirlo). Necesitas [FFmpeg](https://ffmpeg.org/) instalado y accesible, como se explica en el [README](../../README.md#instalación).

## `reduvid probe`

Muestra un resumen legible de uno o más archivos: formato, duración, tamaño, y cada pista de vídeo, audio y subtítulos.

```bash
reduvid probe pelicula.mkv
```

```
File: /ruta/a/pelicula.mkv
Format: matroska,webm
Duration: 1:42:30
Size: 4521.30 MB
Video 1: hevc, 3840x2160, 24 fps, 10-bit, HDR yes (hdr10)
Audio 1: eac3, 6 channels, eng
Audio 2: aac, 2 channels, spa
Subtitle 1: subrip, eng, image: no
```

Puedes pasar varios archivos a la vez; si uno falla al analizarse, se muestra el error y se sigue con los demás.

## `reduvid convert`

Convierte uno o más archivos, o una carpeta entera.

```bash
reduvid convert pelicula.mkv
reduvid convert carpeta/ --recursive
reduvid convert *.mkv --target modern --quality max_savings
reduvid convert pelicula.mkv --keep-audio ca,es --keep-subs ca,und
```

Por defecto, el archivo convertido se escribe junto al original con el sufijo `_reduvid` (por ejemplo `pelicula_reduvid.mkv`), sin tocar el archivo de partida. El original solo se envía a la papelera si pasas `--replace-original`, y solo después de comprobar que la conversión es correcta.

### Opciones

| Opción | Valores | Por defecto | Qué hace |
| --- | --- | --- | --- |
| `--target` | `jellyfin`, `modern`, `archive` | `jellyfin` | Perfil de destino. `jellyfin` prioriza que se reproduzca directo en Jellyfin (H.264); `modern` usa H.265 para más ahorro; `archive` es H.265 con compresión máxima y más lento. |
| `--quality` | `high`, `balanced`, `max_savings` | `balanced` | Nivel de calidad/tamaño. Ver la tabla de CRF en el [README](../../README.md). |
| `--container` | `mkv`, `mp4` | `mkv` | Formato del archivo de salida. |
| `--keep-audio` | idiomas separados por comas | todas | Conserva solo las pistas de audio de esos idiomas; `und` es «sin idioma». Si ninguna coincide, se conservan todas y se avisa. |
| `--keep-subs` | idiomas separados por comas | todos | Conserva solo los subtítulos de esos idiomas (`und` es «sin idioma»). Puede no quedar ninguno. |
| `--max-height` | número entero | `1080` (en `jellyfin`) | Fuerza una altura máxima distinta de 1080p. Solo tiene efecto en el perfil `jellyfin`. |
| `--output-dir` | carpeta | la del original | Dónde se escriben los archivos convertidos. |
| `--recursive` | — | desactivado | Si el argumento es una carpeta, busca vídeos también en sus subcarpetas. |
| `--threads` | número entero | el que decida FFmpeg | Número de hilos de codificación (`-threads`). |
| `--replace-original` | — | desactivado | Envía el original a la papelera del sistema (nunca lo borra permanentemente) tras verificar que la conversión es correcta. |
| `--dry-run` | — | desactivado | Muestra qué se haría (archivo de salida, decisiones por pista, avisos) sin convertir nada. |

### Modo de prueba (`--dry-run`)

Antes de convertir de verdad, puedes ver el plan exacto que se aplicaría:

```bash
reduvid convert pelicula.mkv --dry-run --target modern --quality high
```

```
Dry run: 1 file(s)
Would convert: /ruta/a/pelicula.mkv
Output: /ruta/a/pelicula_reduvid.mkv
Plan: modern, high, mkv
  Video stream 0: encode, libx265, CRF 21, medium preset
  Audio stream 0: copy
Dry run complete.
```

### Avisos

Durante la conversión pueden aparecer avisos sobre decisiones del plan: reducción de resolución a 1080p, conversión de HDR a SDR (o aviso si FFmpeg no tiene los filtros necesarios), subtítulos de imagen conservados con aviso de que Jellyfin los «quemará», subtítulos de imagen descartados en MP4, o pistas de audio recodificadas. Se muestran tal cual en la salida de la orden.

### Al terminar

Se imprime un resumen de la cola: archivos correctos, fallidos y omitidos, y el ahorro total conseguido:

```
Files: 3 succeeded, 0 failed, 1 skipped
Total savings: 812.40 MB (41.2%)
```

## Configuración

Si FFmpeg no está en el `PATH` del sistema, puedes indicar su ruta en un archivo de configuración TOML en el directorio de configuración del usuario (por ejemplo `~/.config/reduvid/config.toml` en Linux, o `%LOCALAPPDATA%\reduvid\config.toml` en Windows):

```toml
ffmpeg_path = "/ruta/completa/a/ffmpeg"
```

## Códigos de salida

| Código | Significado |
| --- | --- |
| `0` | Todo correcto. |
| `1` | No se encontró FFmpeg o ffprobe. |
| `2` | Algún archivo de entrada no existe, no se pudo analizar, o falló al convertirse. |
