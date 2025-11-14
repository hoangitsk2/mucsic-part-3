"""Utility helpers for downloading audio using yt-dlp."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional


def download_audio(url: str, target_directory: Path, audio_format: str = "mp3") -> Path:
    """Download a single YouTube audio track to the target directory.

    Parameters
    ----------
    url: str
        YouTube URL provided by the user.
    target_directory: Path
        Directory where the audio file will be saved.
    audio_format: str
        Output format supported by yt-dlp/ffmpeg.
    """

    target_directory = Path(target_directory)
    target_directory.mkdir(parents=True, exist_ok=True)

    output_template = str(target_directory / "%(title)s.%(ext)s")
    command = [
        "yt-dlp",
        "-f",
        "bestaudio/best",
        "--extract-audio",
        "--audio-format",
        audio_format,
        "--output",
        output_template,
        url,
    ]

    logging.info("Running yt-dlp for %s", url)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logging.error("yt-dlp failed: %s", result.stderr)
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")

    logging.info("yt-dlp output: %s", result.stdout)
    # yt-dlp reports the output path in stdout. We can't easily capture actual file name without parsing,
    # so return the directory for reference.
    return target_directory


__all__ = ["download_audio"]
