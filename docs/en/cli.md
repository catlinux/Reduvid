# Command-line usage

[Castellano](../es/cli.md) · **English**

`reduvid` has two commands: `probe` (see what's in a video) and `convert` (shrink it). You need [FFmpeg](https://ffmpeg.org/) installed and accessible, as explained in the [README](../../README.en.md#installation).

## `reduvid probe`

Shows a readable summary of one or more files: format, duration, size, and every video, audio and subtitle track.

```bash
reduvid probe movie.mkv
```

```
File: /path/to/movie.mkv
Format: matroska,webm
Duration: 1:42:30
Size: 4521.30 MB
Video 1: hevc, 3840x2160, 24 fps, 10-bit, HDR yes (hdr10)
Audio 1: eac3, 6 channels, eng
Audio 2: aac, 2 channels, spa
Subtitle 1: subrip, eng, image: no
```

You can pass several files at once; if one fails to probe, the error is shown and the rest continue.

## `reduvid convert`

Converts one or more files, or an entire folder.

```bash
reduvid convert movie.mkv
reduvid convert folder/ --recursive
reduvid convert *.mkv --target modern --quality max_savings
```

By default, the converted file is written next to the original with the `_reduvid` suffix (for example `movie_reduvid.mkv`), without touching the source. The original is only sent to the trash if you pass `--replace-original`, and only after checking the conversion is correct.

### Options

| Option | Values | Default | What it does |
| --- | --- | --- | --- |
| `--target` | `jellyfin`, `modern`, `archive` | `jellyfin` | Destination profile. `jellyfin` prioritizes direct playback on Jellyfin (H.264); `modern` uses H.265 for more savings; `archive` is H.265 with maximum compression and a slower preset. |
| `--quality` | `high`, `balanced`, `max_savings` | `balanced` | Quality/size level. See the CRF table in the [README](../../README.en.md). |
| `--container` | `mkv`, `mp4` | `mkv` | Output file format. |
| `--max-height` | integer | `1080` (on `jellyfin`) | Forces a maximum height other than 1080p. Only has an effect on the `jellyfin` profile. |
| `--output-dir` | folder | the original's folder | Where converted files are written. |
| `--recursive` | — | off | If the argument is a folder, also look for videos in its subfolders. |
| `--threads` | integer | FFmpeg's own choice | Number of encoding threads (`-threads`). |
| `--replace-original` | — | off | Sends the original to the system trash (never deletes it permanently) once the conversion has been verified. |
| `--dry-run` | — | off | Shows what would happen (output file, per-track decisions, warnings) without converting anything. |

### Dry run (`--dry-run`)

Before actually converting, you can see the exact plan that would be applied:

```bash
reduvid convert movie.mkv --dry-run --target modern --quality high
```

```
Dry run: 1 file(s)
Would convert: /path/to/movie.mkv
Output: /path/to/movie_reduvid.mkv
Plan: modern, high, mkv
  Video stream 0: encode, libx265, CRF 21, medium preset
  Audio stream 0: copy
Dry run complete.
```

### Warnings

During conversion you may see warnings about plan decisions: resolution reduced to 1080p, HDR converted to SDR (or a warning if FFmpeg lacks the needed filters), image subtitles kept with a warning that Jellyfin will "burn" them in, image subtitles dropped in MP4, or audio tracks re-encoded. They are printed as-is in the command's output.

### When it finishes

A queue summary is printed: succeeded, failed and skipped files, and the total savings achieved:

```
Files: 3 succeeded, 0 failed, 1 skipped
Total savings: 812.40 MB (41.2%)
```

## Configuration

If FFmpeg is not on the system `PATH`, you can set its path in a TOML configuration file under the user's config directory (for example `~/.config/reduvid/config.toml` on Linux, or `%LOCALAPPDATA%\reduvid\config.toml` on Windows):

```toml
ffmpeg_path = "/full/path/to/ffmpeg"
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Everything succeeded. |
| `1` | FFmpeg or ffprobe were not found. |
| `2` | Some input file does not exist, could not be probed, or failed to convert. |
