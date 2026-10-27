# Reduvid

[Castellano](README.md) · **English**

Easy, cross-platform video compressor built for [Cinecat](https://github.com/catlinux/Cinecat) libraries, the author's media server: shrink files with H.264/H.265 while keeping subtitles and chapters. Step-by-step wizard. Powered by FFmpeg.

## What it is

Reduvid (from *reducir vídeo*, Spanish for "shrink video") is a desktop app for Linux and Windows that makes your videos smaller with very little quality loss. It uses [FFmpeg](https://ffmpeg.org/) under the hood, but you don't need to know anything about codecs: a wizard asks where you'll watch the videos and how much space you want to save, and explains every option in plain language.

- **Your originals stay untouched.** Reduvid writes a new file, checks that it is complete, and only then gives it its final name. It never overwrites anything.
- **Built for Cinecat.** A "Cinecat" profile produces MP4 with 8-bit H.264 that Cinecat direct-plays in the browser, without the server having to convert it.
- **Keeps what matters:** subtitles, chapters, audio tracks and languages, metadata and cover art.
- **For everyone:** Wizard mode (one decision per screen), Advanced mode (everything in one view), and a command line for servers and scripts.

## Project status

In development. The current version (0.5.2) already has a graphical interface, a step-by-step wizard and a command line. Plan:

| Version | Contents |
|---|---|
| 0.1.0 | Conversion engine and command line |
| 0.2.0 | Graphical interface, wizard and languages (Català, Castellano, English) |
| 0.3.0 | Choose audio tracks one by one, reduce the audio size and see how much each part weighs |
| 0.4.0 | Sample test: estimated size and time before converting |
| 0.5.0 | Clear video options: what changes, estimated size per quality level and resolution |
| 0.6.0 | Final report, saved profiles and warnings for HDR, 10-bit video and image subtitles |
| 0.7.0 → 1.0.0 | Linux and Windows installers and first stable release |

Details in [TODO.en.md](TODO.en.md) and the [CHANGELOG](CHANGELOG.en.md).

## Screenshots

The wizard, in its three interchangeable themes; **Plegat** is the default theme. More screenshots and the full interface walkthrough in the [graphical interface guide](docs/en/gui.md).

| Plegat | Riso | Cinta |
|---|---|---|
| [![Reduvid with the Plegat theme](docs/screenshots/plegat_light.png)](docs/screenshots/plegat_light.png) | [![Reduvid with the Riso theme](docs/screenshots/riso_light.png)](docs/screenshots/riso_light.png) | [![Reduvid with the Cinta theme](docs/screenshots/cinta_light.png)](docs/screenshots/cinta_light.png) |

<details>
<summary>Dark mode</summary>

| Plegat | Riso | Cinta |
|---|---|---|
| [![Reduvid with the Plegat theme in dark mode](docs/screenshots/plegat_dark.png)](docs/screenshots/plegat_dark.png) | [![Reduvid with the Riso theme in dark mode](docs/screenshots/riso_dark.png)](docs/screenshots/riso_dark.png) | [![Reduvid with the Cinta theme in dark mode](docs/screenshots/cinta_dark.png)](docs/screenshots/cinta_dark.png) |

</details>

Original design mockups in [docs/design/mockups.html](docs/design/mockups.html).

## Requirements

- Linux or Windows 10/11.
- Python 3.11 or later, until installers exist.
- **FFmpeg** with `libx264` and `libx265`. Reduvid does not include it: it uses the one you have installed.

## Installation

1. Install FFmpeg:
   - Debian / Ubuntu: `sudo apt install ffmpeg`
   - Windows: `winget install Gyan.FFmpeg`, or download it from [ffmpeg.org](https://ffmpeg.org/download.html) and add it to your `PATH`.
2. Install Reduvid from source:

   ```bash
   git clone https://github.com/catlinux/Reduvid.git
   cd Reduvid
   # On Debian/Ubuntu the command is python3 (if it fails: sudo apt install python3-venv)
   python3 -m venv .venv          # Windows: py -m venv .venv
   source .venv/bin/activate    # Windows: .venv\Scripts\activate
   python -m pip install -e .
   ```

To build a Windows installer or a Linux AppImage instead of running from source, see the [installers guide](docs/en/instalacion.md). The `pipx` package will come later.

## Quick start

`reduvid` opens the graphical interface. The command line is `reduvid-cli`:

```bash
reduvid-cli probe video.mkv              # See what a video contains
reduvid-cli convert video.mkv            # Convert it with the default Cinecat profile
reduvid-cli convert folder/ --recursive  # Convert an entire folder
```

Interface guide (wizard and Advanced mode) in [docs/en/gui.md](docs/en/gui.md). Full details on commands, options and exit codes in the [command-line guide](docs/en/cli.md).

## H.264 or H.265 for Cinecat?

| | 8-bit H.264 in MP4 ("Cinecat") | H.265 / HEVC ("modern") |
|---|---|---|
| Typical savings | 20-40 % | 40-70 % |
| Direct play in Cinecat | Yes, in the browser | No: Cinecat converts it while you watch |
| Choose it if | You watch in the browser, or you're not sure | Your devices are modern, or you only want to archive |

Cinecat only direct-plays MP4 in the browser. 8-bit H.264 in MP4 is what works in every browser; for Cinecat not to convert anything, the video must be 8-bit H.264 up to 1080p, and the audio AAC or MP3. The Cinecat profile already prepares it that way, converts HDR to SDR and drops image subtitles with a warning. H.265 takes less space, but Cinecat will have to convert it while you watch, using the server's CPU. These figures are rough and depend on each video; Reduvid's sample test (since 0.4.0) gives the real number.

## Privacy

Reduvid has no telemetry or usage statistics and does not connect to the internet. Everything happens on your computer.

## FFmpeg and licensing

Reduvid does not include or distribute FFmpeg or any codec. It runs FFmpeg as a separate program, passing it arguments, without linking or bundling its libraries. FFmpeg builds with `libx264` and `libx265` are usually GPL-licensed; that license governs FFmpeg, not Reduvid. If you redistribute FFmpeg (for example, alongside Reduvid), complying with its license is up to you. In some countries H.264 and H.265 are covered by patents.

Dependency licenses are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Contributing

Contributions are welcome, translations included. Please read [CONTRIBUTING.en.md](CONTRIBUTING.en.md) and the [code of conduct](CODE_OF_CONDUCT.md). To report a security issue, see [SECURITY.md](SECURITY.md).

## Credits and license

**Reduvid** is developed and maintained by **Catlinux** ([github.com/catlinux](https://github.com/catlinux)).
Copyright (C) 2026 Catlinux.

Licensed under [WNCL-CU-1.0](LICENSE): free to use for any purpose, including commercial work, and to modify and share at no cost. No one may charge for the software or its use; only support and implementation services may be paid. It is not an OSI-approved Open Source license.

Copies and forks must keep this attribution and link to https://github.com/catlinux/Reduvid.

### Third-party material

| Component | Author | License | Link |
| --- | --- | --- | --- |

This repository contains no third-party material. Dependencies installed separately keep their own licenses and are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
