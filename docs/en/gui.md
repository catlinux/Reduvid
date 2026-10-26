# Using the graphical interface

[Castellano](../es/gui.md) · **English**

Open it with `reduvid` (or `python -m reduvid`). For servers without a screen, use the [command line](cli.md) (`reduvid-cli`).

## Screenshots

The wizard's Summary step, in all three themes (paths relative to this guide):

| Plegat | Riso | Cinta |
|---|---|---|
| [![Plegat theme](../screenshots/plegat_light.png)](../screenshots/plegat_light.png) | [![Riso theme](../screenshots/riso_light.png)](../screenshots/riso_light.png) | [![Cinta theme](../screenshots/cinta_light.png)](../screenshots/cinta_light.png) |
| [![Plegat theme, dark mode](../screenshots/plegat_dark.png)](../screenshots/plegat_dark.png) | [![Riso theme, dark mode](../screenshots/riso_dark.png)](../screenshots/riso_dark.png) | [![Cinta theme, dark mode](../screenshots/cinta_dark.png)](../screenshots/cinta_dark.png) |

## First start

Reduvid needs FFmpeg. If it cannot find it (neither at the configured path nor on the `PATH`), it shows a screen explaining how to install it (`winget install Gyan.FFmpeg` on Windows; `apt` or `dnf` on Linux) and offers **Choose ffmpeg…** to point to the executable and **Search again**. It never uses the network.

## Wizard mode

One decision per screen. At the top you can switch to Advanced mode and back without losing your choices.

1. **Videos.** Add files or a folder (with the checkbox to include subfolders), or drag them onto the window. Reduvid analyses them in the background and shows each duration, or the error if a file cannot be read. You can remove the ones you do not want. You need at least one successfully analysed video to continue.
2. **Where will you watch them?** Pick the destination: *Jellyfin* (TV, phone or browser; H.264, the most compatible), *Modern devices* (H.265, more savings) or *Save for archive* (H.265 with more compression, slower). “I don't know” uses Jellyfin.
3. **Quality.** *Almost identical*, *Balanced* (recommended) or *Maximum savings*. The “What is this?” drop-down explains the trade-off between quality and size. This version does not show estimated sizes yet.
4. **What to keep.** With a single video you choose the audio tracks one by one: you see each language, format, channels and estimated size, and the default track carries a label. Subtitles are chosen by language and show whether they are text or image. With several videos you choose the audio and subtitle languages; “One audio track per language” keeps the best track of each language. In both cases, “Reduce the audio size” re-encodes the audio to AAC (compatible with MP4 and MKV) and a line shows how much it will weigh before and after; it is an estimate. If the chosen container drops image subtitles or makes Jellyfin burn them in, a note warns you. If you do not tick any audio track, all of them are kept and you are warned.
5. **Destination.** The same folder as each video or another one, MKV or MP4 and, if there is 4K video with the Jellyfin destination, the option to reduce it to 1080p. **Replace the original** is off by default: if you turn it on, the original goes to the recycle bin only once the copy has been verified.
6. **Summary.** Review what Reduvid will do with each video before starting. The "Estimate the final size (1-minute test)" button converts three 20-second chunks of the video (around 20 %, 50 % and 80 %) with your settings, saves nothing, and works out how big the final file will be and how long it will take. It is an estimate: the real size can differ if the video changes a lot between scenes. If you change any setting, estimate again.

### The Jellyfin traffic light

Each video in the summary carries an indicator:

| Colour | Meaning |
| --- | --- |
| Green | It will direct-play in Jellyfin, without the server converting it |
| Amber | Something will make Jellyfin convert the video during playback (H.265 destination, 10-bit, or image subtitles it will have to “burn in”) |
| Red | A warning needs your decision |

If a video is HDR and your FFmpeg cannot turn it into SDR, Reduvid asks you for each one: **Skip this video** (default) or **Convert anyway** (colours will look washed out). Skipped videos do not enter the queue.

**Start** launches the conversion and opens the queue panel.

## Advanced mode

A single page with every command-line option: videos, destination, quality, container, maximum height, output folder, number of threads, replace the original and languages, plus the same summary with the traffic light. It shares its selection with the wizard. You cannot switch modes while a conversion is running.

## Queue panel

On the right (below, in narrow windows) you see the current video with its percentage and remaining time, the list of videos with their warnings, and the **Pause** / **Resume** and **Cancel** buttons. Cancelling leaves no half-written file behind. If you close the window while a conversion is running, Reduvid asks before cancelling it. When it finishes it shows the total savings and, for each error, a clear message with a drop-down of technical details you can copy.

## Preferences

- **Theme:** Plegat (default), Riso or Cinta.
- **Colour mode:** System (default), Light or Dark.
- **Language:** System, català, castellano or English. It applies after a restart.
- **Reduce animations.**
- **FFmpeg path:** with **Browse…** and **Check**.

They are saved in the configuration file, the same one the command line uses (see [the CLI guide](cli.md)).
