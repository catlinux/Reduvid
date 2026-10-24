# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

"""Human-readable texts for engine warnings and errors."""

from __future__ import annotations

from reduvid.core.plan import Warning
from reduvid.i18n import _


def warning_text(warning: Warning) -> str:
    """Return a clear sentence describing *warning*."""
    templates = {
        "resolution_reduced_4k_to_1080p": _(
            "Video track {stream_index} will be scaled down to 1080p so that "
            "Jellyfin can play it directly."
        ),
        "hdr_converted_to_sdr": _(
            "Video track {stream_index} is HDR and will be converted to SDR; "
            "colours may look slightly different."
        ),
        "hdr_tonemap_unavailable": _(
            "Video track {stream_index} is HDR and this FFmpeg installation "
            "cannot convert it to SDR."
        ),
        "audio_recoded": _(
            "Audio track {stream_index} will be converted to {codec} so that "
            "Jellyfin can play it directly."
        ),
        "image_subtitle_burn_in": _(
            "Image subtitle track {stream_index} will have to be converted "
            "while playing, which uses more CPU."
        ),
        "image_subtitle_dropped_mp4": _(
            "Image subtitle track {stream_index} cannot be stored in MP4 and will be removed."
        ),
        "audio_filter_kept_all": _(
            "No audio track matches the selected languages, so all of them will be kept."
        ),
        "not_direct_play_profile": _(
            "{destination} output is not the Jellyfin profile, so Jellyfin may have to "
            "transcode it."
        ),
        "ten_bit_video": _(
            "Video track {stream_index} is 10-bit, which some Jellyfin clients cannot "
            "play directly."
        ),
    }
    template = templates.get(warning.code)
    if template is None:
        return _("Unknown warning: {code}").format(code=warning.code)
    try:
        return template.format(**warning.params)
    except (KeyError, IndexError, ValueError):
        return _("Unknown warning: {code}").format(code=warning.code)


def error_text(code: str) -> str:
    """Return a clear sentence for an engine or queue error code."""
    templates = {
        "no_space": _("There is not enough free space on the destination drive."),
        "corrupt_input": _("The file appears to be damaged and could not be read."),
        "missing_codec": _(
            "This FFmpeg installation is missing an encoder that is needed to convert the file."
        ),
        "permission_denied": _(
            "The file or folder cannot be read or written because of a permissions problem."
        ),
        "cancelled": _("The conversion was cancelled."),
        "verification_failed": _(
            "The converted file did not pass the safety checks and was discarded."
        ),
        "probe_failed": _(
            "The file could not be analysed. It may be damaged or in an unsupported format."
        ),
        "unknown": _("Something went wrong while processing the file."),
    }
    return templates.get(code, templates["unknown"])
