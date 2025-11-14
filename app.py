"""Main entry point for the Raspberry Pi recess music scheduler."""
from __future__ import annotations

import argparse
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import subprocess

import schedule
from flask import Flask, jsonify, redirect, render_template, request, url_for

from utils.music_player import MusicPlayer
from utils.youtube_downloader import download_audio


@dataclass
class ScheduleEntry:
    """Represents a single recess schedule."""

    label: str
    start_time: str
    duration_minutes: int
    shutdown_after: bool = True


@dataclass
class AppConfig:
    """Holds configuration loaded from config.json."""

    music_directory: Path
    log_file: Path
    schedules: List[ScheduleEntry]
    shutdown_command: str
    web_enabled: bool = True
    web_host: str = "0.0.0.0"
    web_port: int = 5000
    youtube_audio_format: str = "mp3"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        schedules = [
            ScheduleEntry(
                label=entry.get("label", f"Schedule {idx+1}"),
                start_time=entry["start_time"],
                duration_minutes=int(entry["duration_minutes"]),
                shutdown_after=bool(entry.get("shutdown_after", True)),
            )
            for idx, entry in enumerate(data.get("schedules", []))
        ]

        web = data.get("web", {})
        youtube = data.get("youtube", {})

        return cls(
            music_directory=Path(data.get("music_directory", "playlist")),
            log_file=Path(data.get("log_file", "logs/app.log")),
            schedules=schedules,
            shutdown_command=data.get("shutdown_command", "sudo shutdown now"),
            web_enabled=bool(web.get("enabled", True)),
            web_host=web.get("host", "0.0.0.0"),
            web_port=int(web.get("port", 5000)),
            youtube_audio_format=youtube.get("audio_format", "mp3"),
        )


class RecessScheduler:
    """Coordinates schedule execution, playback, and shutdown."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.player = MusicPlayer(config.music_directory)
        self._current_session: Optional[str] = None
        self._lock = threading.Lock()

    def schedule_jobs(self) -> None:
        """Register every recess schedule with the schedule library."""
        schedule.clear()
        for entry in self.config.schedules:
            logging.info("Scheduling %s at %s for %s minutes", entry.label, entry.start_time, entry.duration_minutes)
            schedule.every().day.at(entry.start_time).do(self._start_session_threaded, entry)

    def _start_session_threaded(self, entry: ScheduleEntry) -> None:
        threading.Thread(target=self._run_session, args=(entry,), daemon=True).start()

    def start_manual_session(self, duration_minutes: int, shutdown_after: bool = False, label: str = "Manual") -> bool:
        """Allows manual triggering via the web interface."""
        with self._lock:
            if self._current_session:
                logging.warning("Cannot start manual session while %s is running", self._current_session)
                return False
            entry = ScheduleEntry(label=label, start_time="manual", duration_minutes=duration_minutes, shutdown_after=shutdown_after)
            threading.Thread(target=self._run_session, args=(entry,), daemon=True).start()
            return True

    def stop_session(self) -> None:
        self.player.stop()

    def _run_session(self, entry: ScheduleEntry) -> None:
        with self._lock:
            if self._current_session:
                logging.info("Session %s already running, skipping %s", self._current_session, entry.label)
                return
            self._current_session = entry.label

        logging.info("Starting session: %s", entry.label)
        try:
            self.player.play_for_duration(entry.duration_minutes)
        finally:
            logging.info("Session %s finished", entry.label)
            with self._lock:
                self._current_session = None

        if entry.shutdown_after:
            self.shutdown_pi()

    def shutdown_pi(self) -> None:
        """Issue the shutdown command to power off the Raspberry Pi."""
        logging.info("Executing shutdown command: %s", self.config.shutdown_command)
        try:
            subprocess.Popen(self.config.shutdown_command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as exc:  # pragma: no cover - hardware dependent
            logging.error("Failed to execute shutdown command: %s", exc)

    def run_forever(self) -> None:
        """Run schedule loop indefinitely."""
        while True:
            schedule.run_pending()
            time.sleep(1)

    def list_tracks(self) -> List[str]:
        return self.player.list_tracks()

    @property
    def current_session(self) -> Optional[str]:
        with self._lock:
            return self._current_session


def create_web_app(scheduler: RecessScheduler, config: AppConfig) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        tracks = scheduler.list_tracks()
        return render_template(
            "index.html",
            tracks=tracks,
            current_session=scheduler.current_session,
            schedules=config.schedules,
        )

    @app.post("/control/play")
    def play():
        duration = int(request.form.get("duration", 5))
        ok = scheduler.start_manual_session(duration_minutes=duration, shutdown_after=False, label="Manual Web Session")
        if not ok:
            return ("Session already running", 409)
        return redirect(url_for("index"))

    @app.post("/control/stop")
    def stop():
        scheduler.stop_session()
        return redirect(url_for("index"))

    @app.post("/download")
    def download_track():
        payload = request.get_json(force=True)
        url = payload.get("url")
        if not url:
            return jsonify({"error": "Missing url"}), 400
        try:
            file_path = download_audio(url, config.music_directory, config.youtube_audio_format)
        except Exception as exc:  # pragma: no cover - depends on yt-dlp network
            logging.exception("Download failed")
            return jsonify({"error": str(exc)}), 500
        return jsonify({"status": "downloaded", "file": str(file_path)})

    return app


def load_config(path: Path) -> AppConfig:
    with Path(path).open("r", encoding="utf-8") as config_file:
        data = json.load(config_file)
    return AppConfig.from_dict(data)


def setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Recess music automation")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--no-web", action="store_true", help="Disable the Flask web interface")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    setup_logging(config.log_file)

    scheduler = RecessScheduler(config)
    scheduler.schedule_jobs()

    if config.web_enabled and not args.no_web:
        web_app = create_web_app(scheduler, config)
        threading.Thread(
            target=web_app.run,
            kwargs={"host": config.web_host, "port": config.web_port},
            daemon=True,
        ).start()

    scheduler.run_forever()


if __name__ == "__main__":
    main()
