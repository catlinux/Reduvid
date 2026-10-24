# To do

[Castellano](TODO.md) · **English**

The detailed plan for each step is in [.agents/plans/reduvid/reduvid.PLAN.md](.agents/plans/reduvid/reduvid.PLAN.md) (in Spanish).

## High priority

- Decide how external code contributions are licensed before accepting the first one: the license only covers material owned by Catlinux.
- 0.2.0, interface: Wizard and Advanced modes, contextual explanations, ca/es/en languages and accessibility.

## Medium priority

- 0.3.0, helpers: sample test, estimates, final report, saved profiles and warnings for HDR, 10-bit video and image subtitles.
- 0.4.0 → 1.0.0: pipx, Windows installer, AppImage, screenshots and first release.
- When creating the GitHub repository: "About" description, topics (`video`, `ffmpeg`, `jellyfin`, `h264`, `h265`, `video-compression`, `pyside6`, `cross-platform`) and private vulnerability reporting enabled.

## Low priority / later

- AV1 (libsvtav1): the profile architecture already allows it; the profile, tests and explanation are missing.
- Polished hardware acceleration (NVENC, QSV, VAAPI): in 0.1.0 it is only detected and reported.
- The other design directions as selectable themes.
- A target profile for the author's own playback platform, once it exists.
- OCR of image subtitles into text (would need Tesseract as an external tool).
- .deb and Flatpak packages.
- macOS: not a goal for now; don't break it without reason.
- More interface languages.

## Discarded

- **Shipping FFmpeg in the repository or packages:** for licensing (GPL of libx264/libx265) and size reasons. The system's FFmpeg is used.
- **Tkinter:** it doesn't allow the distinctive design the project wants.
- **Full PySide6 (with Addons):** much heavier and unnecessary; PySide6-Essentials is enough.
- **Telemetry or online update checks:** the program does not connect to the network.
