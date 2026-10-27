# Uso de la línea de órdenes

**Castellano** · [English](../en/cli.md)

`reduvid-cli` tiene tres órdenes: `probe` (ver qué contiene un vídeo), `convert` (reducirlo) y `estimate` (calcular cuánto pesará y cuánto tardará antes de convertirlo). La interfaz gráfica se abre con `reduvid`. Necesitas [FFmpeg](https://ffmpeg.org/) instalado y accesible, como se explica en el [README](../../README.md#instalación).

## `reduvid-cli probe`

Muestra un resumen legible de uno o más archivos: formato, duración, tamaño, y cada pista de vídeo, audio y subtítulos.

```bash
reduvid-cli probe pelicula.mkv
```

```
File: /ruta/a/pelicula.mkv
Format: matroska,webm
Duration: 1:42:30
Size: 4521.30 MB
Video 1: hevc, 3840x2160, 24 fps, 10-bit, HDR yes (hdr10)
Audio 1: eac3, 6 channels, eng, ~492 MB estimated
Audio 2: aac, 2 channels, spa, ~98 MB estimated
Subtitle 1: subrip, eng, image: no
```

Puedes pasar varios archivos a la vez; si uno falla al analizarse, se muestra el error y se sigue con los demás.

## `reduvid-cli convert`

Convierte uno o más archivos, o una carpeta entera.

```bash
reduvid-cli convert pelicula.mkv
reduvid-cli convert carpeta/ --recursive
reduvid-cli convert *.mkv --target modern --quality max_savings
reduvid-cli convert pelicula.mkv --keep-audio ca,es --keep-subs ca,und
reduvid-cli convert pelicula.mkv --audio-tracks 1,3 --reduce-audio
```

Por defecto, el archivo convertido se escribe junto al original con el sufijo `_reduvid` (por ejemplo `pelicula_reduvid.mkv`), sin tocar el archivo de partida. El original solo se envía a la papelera si pasas `--replace-original`, y solo después de comprobar que la conversión es correcta.

### Opciones

| Opción | Valores | Por defecto | Qué hace |
| --- | --- | --- | --- |
| `--target` | `jellyfin`, `modern`, `archive` | `jellyfin` | Perfil de destino. `jellyfin` prioriza que se reproduzca directo en Jellyfin (H.264); `modern` usa H.265 para más ahorro; `archive` es H.265 con compresión máxima y más lento. |
| `--quality` | `high`, `balanced`, `max_savings` | `balanced` | Nivel de calidad/tamaño. Ver la tabla de CRF en el [README](../../README.md). |
| `--container` | `mkv`, `mp4` | `mkv` | Formato del archivo de salida. |
| `--audio-tracks` | índices separados por comas | todas | Conserva solo las pistas de audio con esos índices de ffprobe (`0`, `1`...). Tiene prioridad sobre `--keep-audio`. |
| `--one-audio-per-language` | — | desactivado | Conserva solo la pista de audio de mejor calidad para cada idioma (canales, bitrate y marca por defecto). |
| `--reduce-audio` | — | desactivado | Recodifica las pistas de audio a AAC (256 kbps multicanal, 128 kbps estéreo) para ahorrar espacio. |
| `--keep-audio` | idiomas separados por comas | todas | Conserva solo las pistas de audio de esos idiomas; `und` es «sin idioma». Si ninguna coincide, se conservan todas y se avisa. |
| `--keep-subs` | idiomas separados por comas | todos | Conserva solo los subtítulos de esos idiomas (`und` es «sin idioma»). Puede no quedar ninguno. |
| `--max-height` | número entero | `1080` (en `jellyfin`) | Altura máxima del vídeo: si el original es más alto se reduce a ese valor; nunca se amplía. Sin esta opción, `jellyfin` baja a 1080p y los demás perfiles conservan la resolución. |
| `--output-dir` | carpeta | la del original | Dónde se escriben los archivos convertidos. |
| `--recursive` | — | desactivado | Si el argumento es una carpeta, busca vídeos también en sus subcarpetas. |
| `--threads` | número entero | el que decida FFmpeg | Número de hilos de codificación (`-threads`). |
| `--no-hw-decode` | — | desactivado (se usa la GPU si existe) | No usa la tarjeta gráfica para leer los vídeos; por defecto se intenta la GPU si existe y se vuelve al procesador si falla. |
| `--replace-original` | — | desactivado | Envía el original a la papelera del sistema (nunca lo borra permanentemente) tras verificar que la conversión es correcta. |
| `--dry-run` | — | desactivado | Muestra qué se haría (archivo de salida, decisiones por pista, avisos) sin convertir nada. |

### Modo de prueba (`--dry-run`)

Antes de convertir de verdad, puedes ver el plan exacto que se aplicaría:

```bash
reduvid-cli convert pelicula.mkv --dry-run --target modern --quality high
```

```
Dry run: 1 file(s)
Would convert: /ruta/a/pelicula.mkv
Output: /ruta/a/pelicula_reduvid.mkv
Plan: modern, high, mkv
  Video stream 0: encode, libx265, CRF 21, medium preset
  Audio stream 0: copy, ~492 MB estimated
Dry run complete.
```

### Avisos

Durante la conversión pueden aparecer avisos sobre decisiones del plan: reducción de resolución a 1080p, conversión de HDR a SDR (o aviso si FFmpeg no tiene los filtros necesarios), subtítulos de imagen conservados con aviso de que Jellyfin los «quemará», subtítulos de imagen descartados en MP4, o pistas de audio recodificadas o reducidas a AAC para ahorrar espacio. Se muestran tal cual en la salida de la orden.

### Al terminar

Se imprime un resumen de la cola: archivos correctos, fallidos y omitidos, y el ahorro total conseguido:

```
Files: 3 succeeded, 0 failed, 1 skipped
Total savings: 812.40 MB (41.2%)
```

## `reduvid-cli estimate`

Calcula el tamaño final y el tiempo de conversión aproximados de uno o más archivos a partir de una muestra de un minuto, sin convertirlos. Acepta las mismas opciones de codificación que `convert` (`--target`, `--quality`, `--container`, `--max-height`, `--keep-audio`, `--audio-tracks`, `--one-audio-per-language`, `--reduce-audio`, `--keep-subs`, `--threads` y `--no-hw-decode`), pero solo archivos, no carpetas.

La muestra es de un minuto repartido en tres trozos de 20 segundos hacia el 20 %, el 50 % y el 80 % del vídeo; los vídeos de menos de 90 segundos usan un único trozo desde el principio. Solo se codifica el vídeo con los ajustes del plan, así que el resultado es una estimación: el tamaño y el tiempo reales pueden variar según el contenido. No hace falta `--dry-run`: esta orden nunca convierte el archivo.

```bash
reduvid-cli estimate pelicula.mkv --target modern --quality high
reduvid-cli estimate primera.mkv segunda.mkv
```

```
Estimating [1/1]: /ruta/a/pelicula.mkv
Estimate from a 60-second sample; sizes and time are approximate.
  Video: ~1.2 GB
  Audio: ~492 MB
  Estimated size: ~1.7 GB
  Original size: 4.4 GB
  Savings: 61% (2.7 GB smaller)
  Approximate conversion time: 38:20
```

Si el archivo no indica el bitrate del audio, el total no se puede calcular y solo se muestra la estimación del vídeo. El progreso se dibuja en una sola línea cuando la salida es una terminal; si no, no se muestra. Al pulsar Ctrl+C se cancela la muestra, se borran sus archivos temporales y la orden termina con el código `130`.

## Configuración

Si FFmpeg no está en el `PATH` del sistema, puedes indicar su ruta en un archivo de configuración TOML en el directorio de configuración del usuario (por ejemplo `~/.config/reduvid/config.toml` en Linux, o `%LOCALAPPDATA%\reduvid\config.toml` en Windows):

```toml
ffmpeg_path = "/ruta/completa/a/ffmpeg"
```

También puedes desactivar la decodificación por hardware en la configuración con `hw_decode = false`.

## Códigos de salida

| Código | Significado |
| --- | --- |
| `0` | Todo correcto. |
| `1` | No se encontró FFmpeg o ffprobe. |
| `2` | Algún archivo de entrada no existe, no se pudo analizar, falló al convertirse o no se pudo muestrear. |
| `130` | Se interrumpió con Ctrl+C; los archivos temporales se borran. |
