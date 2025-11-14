"""Music playback helpers for Raspberry Pi."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Iterable, List

try:  # pragma: no cover - pygame not installed in CI
    import pygame
except ImportError:  # pragma: no cover - fallback when pygame missing
    pygame = None


class MusicPlayer:
    """Simple playlist-based music player using pygame."""

    SUPPORTED_EXTENSIONS = (".mp3", ".wav", ".ogg")

    def __init__(self, music_directory: Path) -> None:
        self.music_directory = Path(music_directory)
        self.music_directory.mkdir(parents=True, exist_ok=True)
        self._stop_event = threading.Event()
        if pygame:
            pygame.mixer.init()
        logging.info("Music directory set to %s", self.music_directory)

    def list_tracks(self) -> List[str]:
        return [
            str(path)
            for path in sorted(self.music_directory.iterdir())
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS
        ]

    def play_for_duration(self, duration_minutes: int) -> None:
        """Play tracks sequentially for the specified duration."""
        tracks = self.list_tracks()
        if not tracks:
            logging.warning("Playlist empty at %s", self.music_directory)
            return

        duration_seconds = duration_minutes * 60
        start = time.time()
        index = 0
        self._stop_event.clear()

        logging.info("Playing playlist for %s minutes", duration_minutes)
        while time.time() - start < duration_seconds and not self._stop_event.is_set():
            track = tracks[index % len(tracks)]
            logging.info("Now playing: %s", track)
            self._play_file(Path(track))
            self._wait_for_track_finish(start, duration_seconds)
            index += 1

        self.stop()

    def _wait_for_track_finish(self, start_time: float, duration_seconds: int) -> None:
        while not self._stop_event.is_set():
            if time.time() - start_time >= duration_seconds:
                break
            if pygame:
                if not pygame.mixer.music.get_busy():
                    break
            else:
                # Sleep to simulate track playback when pygame is unavailable
                time.sleep(1)
                break
            time.sleep(0.5)

    def _play_file(self, path: Path) -> None:
        if pygame:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
        else:  # pragma: no cover - fallback for systems without pygame
            logging.info("Simulating playback for %s", path.name)

    def stop(self) -> None:
        self._stop_event.set()
        if pygame:
            pygame.mixer.music.stop()
        logging.info("Playback stopped")


__all__ = ["MusicPlayer"]
