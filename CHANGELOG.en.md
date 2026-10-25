# Changelog

[Castellano](CHANGELOG.md) · **English**

All notable changes to Reduvid are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-10-25

### Added

- Sample and estimation engine: fast 30-second clip reusing the encoding plan (`-ss` before `-i`), single PNG frame extraction and linear extrapolation of final size and encoding time from the sample.
- Saved profiles in the engine: `core/profile_store.py` with listing, loading, atomic saving and deletion of individual TOML profiles in the configuration directory, keeping the real names and the difference between unfiltered languages and an empty set.
- Sample and comparison in the Quality step: a button to try 30 s in the background, before/after frames, estimated total size, savings percentage and invalidation when the quality changes; temporary files use fixed names in the cache.
- Estimates in the Summary step: when a valid sample exists for the chosen quality, each card shows its duration-proportional estimated size and time; without a sample nothing is shown.
- Saved profiles from the Quality step: a dropdown to apply a complete profile and a dialog to save the current combination under a name, with visible errors and nothing created when the name is empty.
- Early warnings in the Quality step: the first available video shows the plan warnings (HDR, 10-bit, image subtitles, etc.) before reaching the Summary, recalculated when options or videos change.

## [0.2.1] - 2026-10-25

### Changed

- Main action buttons use `role=primary` (Start, Next and Choose ffmpeg) and the queue Cancel button uses `role=danger`, instead of the same flat style as every other button; Riso's offset shadow now also applies to primary buttons and recommended option cards show a tinted background.
- In the Summary step, each video changes from a text line with a small badge to a full card tinted by its Jellyfin compatibility level, and the vertical gap that used to be spread between rows is now a single block.

## [0.2.0] - 2026-10-25

### Added

- Interface usage guide in `docs/en/gui.md` and `docs/es/gui.md`.
- Graphical interface skeleton: main window with a top bar, Wizard/Advanced switch, step, content and queue panels (stacked in narrow windows), a preferences dialog (theme, colour mode, language, animations and FFmpeg path with checking) and a help screen when FFmpeg is missing.

- User configuration in `core/config.py`: TOML reading (with the FFmpeg path at the root or under `[ffmpeg] path`, unknown keys ignored and a list of invalid keys) and its own atomic writer.
- Interface fonts (Bricolage Grotesque, Instrument Sans, Archivo, Atkinson Hyperlegible, Barlow, Barlow Condensed and JetBrains Mono), under the SIL OFL 1.1 with their `OFL.txt`; documented in `THIRD_PARTY_NOTICES.md`.
- Per-file processing shared in `core/pipeline.py`, with pause, resume and cancel controls, and errors carrying a code (`cancelled` and `verification_failed`); the conversion queue now also reports each file's error code.
- gettext translation in the engine and the command line: `reduvid/i18n.py` (effective language from `--lang`, the configuration or the system), `reduvid/messages.py` with clear texts for every warning and error, `ca` and `es` catalogs with the reference `.pot`, and the global `--lang {ca,es,en}` option.
- Development scripts to extract and compile the translations, and a Hatch hook that compiles the `.po` files to `.mo` on editable installs and wheel builds.
- Language filtering for audio and subtitles (`--keep-audio`, `--keep-subs`) and a Jellyfin compatibility traffic light in `core/compat.py` (`direct`, `partial`, `blocked`), with new warnings for the destination profile and 10-bit video.
- Interface themes: exact Plegat, Riso and Cinta tokens for light and dark (`gui/theme/tokens.py`), the stylesheet generated from them (`qss.py`), registration of the bundled fonts (`fonts.py`) and a `ThemeManager` that applies theme and mode, including the system one.
- Background work and queue panel: probing and conversion in their own threads with Qt signals, progress with remaining time, pause and resume, cancellation without half-written files, per-video warning chips, estimated total, an error view with technical details and a confirmation when closing with a conversion in progress.
- Assistant steps 1-3: shared wizard state, accessible option cards, done/current/pending step list, Back/Next navigation, adding videos with drag and drop and background probing, destination selection (including "I don't know") and quality selection with a recommendation for the destination and a plain-language CRF explanation.
- Assistant steps 4-6: audio and subtitle language selection with readable names, output folder, container, replacing the original and 4K reduction, per-video summary with a compatibility traffic light, a dialog for blocking HDR videos, starting the conversion and a final report with errors and skipped videos.
- Advanced mode: a single page with every CLI option (videos, destination, quality, container, maximum height, output folder, threads, replacement, languages and the summary with start), sharing the wizard state; the switch keeps the selection, saves `ui_mode` and is blocked while a conversion runs.
- Accessibility: accessible names on every interactive control, per-page tab order, consistent Alt+ shortcuts on the main buttons (also in Catalan and Spanish), visible focus on every control in the six themes and long texts wrapped when the font grows.
- Hand-painted motif specific to each theme: folded corner, accordion bar and origami cat in Plegat; offset shadow, hatched track, cat and variable-width figure in Riso; three-colour stripe, reels and mechanical counter in Cinta. The queue progress bar is painted by hand from the tokens and uses no timers, so it honours "Reduce animations".
- Interface screenshots in `docs/screenshots/` (all three themes, light and dark), linked from the README and the interface guide.

### Changed

- `reduvid` now opens the graphical interface and the command line is `reduvid-cli`; the usage documentation has been updated.
- The interface forces the Qt Fusion style so the focus ring and the rest of the stylesheet apply the same way on every platform, instead of depending on the native style.

### Fixed

- The window's initial size is clamped to the available screen, so high scaling (150%, 200%) no longer leaves it wider than the desktop.
- Two Catalan strings that used "guardar" instead of "desar", to match the rest of the catalog.

## [0.1.0] - 2026-10-24

### Added

- Conversion engine (`reduvid.core`), with no Qt dependencies: FFmpeg detection and capability inspection, ffprobe-based media probing (video, audio, subtitles, chapters, attachments and cover art, HDR10/HLG/Dolby Vision), destination profiles (`jellyfin`, `modern`, `archive`) and a per-track encoding plan with typed warnings, FFmpeg argument construction, collision-free output naming without overwriting, duration/size verification after conversion, and controlled execution with progress, pause, cancellation without orphaned files, and low priority.
- Sequential conversion queue with duration-weighted progress and a final savings report.
- Command line: `reduvid probe` (readable summary of a video) and `reduvid convert` (conversion with `--target`, `--quality`, `--container`, `--max-height`, `--output-dir`, `--recursive`, `--threads`, `--replace-original` and `--dry-run`), reading the FFmpeg path from a configuration file when it isn't on the `PATH`.
- End-to-end integration tests against real FFmpeg (videos generated with `lavfi`), in addition to the unit test suite for each engine module.
- Command-line usage guide in Spanish and English (`docs/{es,en}/cli.md`).
- Design mockup screenshots in the README.

## [0.0.1] - 2026-10-24

### Added

- Initial project structure: Python package with `reduvid --version`, tests, ruff, mypy, pre-commit and continuous integration on Linux and Windows.
- WNCL-CU-1.0 license, authorship and third-party notices.
- Base documentation in Spanish and English (README, CHANGELOG, TODO, contributing guide, security policy and code of conduct), plus an automatic check that both versions share the same structure.
- Phased roadmap and mockups of three design directions: Riso, Cinta and Plegat (chosen as interchangeable themes, with Plegat as the default).
- Code contribution policy under DCO (Developer Certificate of Origin).
