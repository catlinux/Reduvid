# Command-line usage

[Castellano](../es/cli.md) · **English**

`reduvid-cli` has three commands: `probe` (see what's in a video), `convert` (shrink it) and `estimate` (work out how big and how slow it will be before converting). The graphical interface opens with `reduvid`. You need [FFmpeg](https://ffmpeg.org/) installed and accessible, as explained in the [README](../../README.en.md#installation).

## `reduvid-cli probe`

Shows a readable summary of one or more files: format, duration, size, and every video, audio and subtitle track.

```bash
reduvid-cli probe movie.mkv
```

```
File: /path/to/movie.mkv
Format: matroska,webm
Duration: 1:42:30
Size: 4521.30 MB
Video 1: hevc, 3840x2160, 24 fps, 10-bit, HDR yes (hdr10)
Audio 1: eac3, 6 channels, eng, ~492 MB estimated
Audio 2: aac, 2 channels, spa, ~98 MB estimated
Subtitle 1: subrip, eng, image: no
```

You can pass several files at once; if one fails to probe, the error is shown and the rest continue.

## `reduvid-cli convert`

Converts one or more files, or an entire folder.

```bash
reduvid-cli convert movie.mkv
reduvid-cli convert folder/ --recursive
reduvid-cli convert *.mkv --target modern --quality max_savings
reduvid-cli convert movie.mkv --keep-audio ca,es --keep-subs ca,und
reduvid-cli convert movie.mkv --audio-tracks 1,3 --reduce-audio
```

By default, the converted file is written next to the original with the `_reduvid` suffix (for example `movie_reduvid.mkv`), without touching the source. The original is only sent to the trash if you pass `--replace-original`, and only after checking the conversion is correct.

### Options

| Option | Values | Default | What it does |
| --- | --- | --- | --- |
| `--target` | `jellyfin`, `modern`, `archive` | `jellyfin` | Destination profile. `jellyfin` prioritizes direct playback on Jellyfin (H.264); `modern` uses H.265 for more savings; `archive` is H.265 with maximum compression and a slower preset. |
| `--quality` | `high`, `balanced`, `max_savings` | `balanced` | Quality/size level. See the CRF table in the [README](../../README.en.md). |
| `--container` | `mkv`, `mp4` | `mkv` | Output file format. |
| `--audio-tracks` | comma-separated track indices | all | Keeps only the audio tracks with those ffprobe indices (`0`, `1`...). Overrides `--keep-audio`. |
| `--one-audio-per-language` | — | off | Keeps only the highest-quality audio track for each language (channels, bitrate and default flag). |
| `--reduce-audio` | — | off | Re-encodes audio tracks to AAC (256 kbps multichannel, 128 kbps stereo) to save space. |
| `--keep-audio` | comma-separated languages | all | Keeps only the audio tracks in those languages; `und` means "no language". If none match, all are kept and a warning is shown. |
| `--keep-subs` | comma-separated languages | all | Keeps only the subtitles in those languages (`und` means "no language"). There may be none left. |
| `--max-height` | integer | `1080` (on `jellyfin`) | Maximum video height: if the source is taller it is scaled down to this value; it never scales up. Without it, `jellyfin` scales down to 1080p and the other profiles keep the resolution. |
| `--output-dir` | folder | the original's folder | Where converted files are written. |
| `--recursive` | — | off | If the argument is a folder, also look for videos in its subfolders. |
| `--threads` | integer | FFmpeg's own choice | Number of encoding threads (`-threads`). |
| `--replace-original` | — | off | Sends the original to the system trash (never deletes it permanently) once the conversion has been verified. |
| `--dry-run` | — | off | Shows what would happen (output file, per-track decisions, warnings) without converting anything. |

### Dry run (`--dry-run`)

Before actually converting, you can see the exact plan that would be applied:

```bash
reduvid-cli convert movie.mkv --dry-run --target modern --quality high
```

```
Dry run: 1 file(s)
Would convert: /path/to/movie.mkv
Output: /path/to/movie_reduvid.mkv
Plan: modern, high, mkv
  Video stream 0: encode, libx265, CRF 21, medium preset
  Audio stream 0: copy, ~492 MB estimated
Dry run complete.
```

### Warnings

During conversion you may see warnings about plan decisions: resolution reduced to 1080p, HDR converted to SDR (or a warning if FFmpeg lacks the needed filters), image subtitles kept with a warning that Jellyfin will "burn" them in, image subtitles dropped in MP4, or audio tracks re-encoded or reduced to AAC to save space. They are printed as-is in the command's output.

### When it finishes

A queue summary is printed: succeeded, failed and skipped files, and the total savings achieved:

```
Files: 3 succeeded, 0 failed, 1 skipped
Total savings: 812.40 MB (41.2%)
```

## `reduvid-cli estimate`

Estimates the final size and conversion time of one or more files from a one-minute sample, without converting them. It accepts the same encoding options as `convert` (`--target`, `--quality`, `--container`, `--max-height`, `--keep-audio`, `--audio-tracks`, `--one-audio-per-language`, `--reduce-audio`, `--keep-subs` and `--threads`), but only files, not folders.

The sample is one minute split into three 20-second chunks at 20%, 50% and 80% of the video; videos shorter than 90 seconds use a single chunk from the start. Only the video is encoded with the plan's settings, so the result is an estimate: the actual size and time may vary depending on the content. There is no need for `--dry-run`: this command never converts the file.

```bash
reduvid-cli estimate movie.mkv --target modern --quality high
reduvid-cli estimate first.mkv second.mkv
```

```
Estimating [1/1]: /path/to/movie.mkv
Estimate from a 60-second sample; sizes and time are approximate.
  Video: ~1.2 GB
  Audio: ~492 MB
  Estimated size: ~1.7 GB
  Original size: 4.4 GB
  Savings: 61% (2.7 GB smaller)
  Approximate conversion time: 38:20
```

If the file does not report an audio bitrate, the total cannot be calculated and only the video estimate is shown. Progress is drawn on a single line when the output is a terminal; otherwise nothing is shown. Ctrl+C cancels the sample, deletes its temporary files and exits with code `130`.

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
| `2` | Some input file does not exist, could not be probed, failed to convert, or could not be sampled. |
| `130` | The command was interrupted with Ctrl+C; temporary files are deleted. |
