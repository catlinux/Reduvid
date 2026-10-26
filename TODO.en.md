# To do

[Castellano](TODO.md) · **English**

The detailed plan for each step is in [.agents/plans/reduvid/reduvid.PLAN.md](.agents/plans/reduvid/reduvid.PLAN.md) (in Spanish).

## High priority

- Decide how external code contributions are licensed before accepting the first one: the license only covers material owned by Catlinux.
- 0.6.0, helpers: final report, saved profiles and warnings for HDR, 10-bit video and image subtitles in the interface.

## Medium priority

- 0.7.0 → 1.0.0: pipx, Windows installer, AppImage, screenshots and first release.
- When creating the GitHub repository: "About" description, topics (`video`, `ffmpeg`, `jellyfin`, `h264`, `h265`, `video-compression`, `pyside6`, `cross-platform`) and private vulnerability reporting enabled.

## Low priority / later

- Before/after frame comparison in the sample test.
- Measure the real error margin of the estimate (compare with the full conversion) before stating a figure in the docs.
- AV1 (libsvtav1): the profile architecture already allows it; the profile, tests and explanation are missing.
- Polished hardware acceleration (NVENC, QSV, VAAPI): in 0.1.0 it is only detected and reported.
- Qt-free install for Linux servers (`reduvid-cli` only): decide in phase 4 how to split off the PySide6 dependency.
- A target profile for the author's own playback platform, once it exists.
- OCR of image subtitles into text (would need Tesseract as an external tool).
- .deb and Flatpak packages.
- macOS: not a goal for now; don't break it without reason.
- More interface languages.
- `scripts/screenshots.py` to automate screenshots with offscreen Qt: on this machine the offscreen backend has no fonts registered (0 families) and text would render empty; the 0.2.0 screenshots were taken by hand from the real window.

## Discarded

- **Shipping FFmpeg in the repository or packages:** for licensing (GPL of libx264/libx265) and size reasons. The system's FFmpeg is used.
- **Tkinter:** it doesn't allow the distinctive design the project wants.
- **Full PySide6 (with Addons):** much heavier and unnecessary; PySide6-Essentials is enough.
- **Telemetry or online update checks:** the program does not connect to the network.
