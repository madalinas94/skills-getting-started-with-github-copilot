"""Thin wrappers around the ffmpeg / ffprobe command-line tools."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".tif", ".tiff"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}


class FFmpegError(RuntimeError):
    pass


def binary(name: str) -> str:
    """Path to ffmpeg/ffprobe; MONTAJ_FFMPEG_DIR overrides the PATH lookup."""
    folder = os.environ.get("MONTAJ_FFMPEG_DIR")
    if folder:
        for candidate in (name, name + ".exe"):
            path = Path(folder) / candidate
            if path.exists():
                return str(path)
    found = shutil.which(name)
    if not found:
        raise FFmpegError(
            f"{name} nu a fost găsit. Instalează ffmpeg și adaugă-l în PATH "
            "(sau setează MONTAJ_FFMPEG_DIR)."
        )
    return found


def available() -> bool:
    try:
        binary("ffmpeg")
        binary("ffprobe")
        return True
    except FFmpegError:
        return False


def run(args, cwd=None, timeout=None) -> subprocess.CompletedProcess:
    """Run ffmpeg with the given arguments; raise FFmpegError with the tail of stderr."""
    cmd = [binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", *map(str, args)]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise FFmpegError(f"ffmpeg a eșuat:\n{tail}")
    return proc


def run_progress(args, total_seconds: float, on_progress=None, cwd=None):
    """Run ffmpeg and report progress (0..1) parsed from -progress output."""
    cmd = [binary("ffmpeg"), "-hide_banner", "-nostdin", "-y",
           "-progress", "pipe:1", "-nostats", *map(str, args)]
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    # stderr is drained on a thread so a chatty ffmpeg can't block on a full pipe
    import threading
    err_lines = []
    t = threading.Thread(target=lambda: err_lines.extend(proc.stderr), daemon=True)
    t.start()
    for line in proc.stdout:
        if line.startswith("out_time_us=") and on_progress and total_seconds > 0:
            try:
                us = int(line.split("=", 1)[1])
                on_progress(min(1.0, us / 1e6 / total_seconds))
            except ValueError:
                pass
    proc.wait()
    t.join(timeout=5)
    if proc.returncode != 0:
        tail = "".join(err_lines[-15:])
        raise FFmpegError(f"ffmpeg a eșuat:\n{tail}")


def probe(path) -> dict:
    """Return a compact description of a media file."""
    cmd = [binary("ffprobe"), "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe nu poate citi fișierul: {proc.stderr.strip()[-300:]}")
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    ext = Path(path).suffix.lower()

    if video and (ext in IMAGE_EXT or video.get("codec_name") in {"mjpeg", "png", "webp", "bmp", "tiff"}
                  and float(fmt.get("duration") or 0) < 0.1):
        kind = "image"
    elif video:
        kind = "video"
    elif audio:
        kind = "audio"
    else:
        raise FFmpegError("Fișierul nu conține video, imagine sau audio.")

    width = int(video.get("width", 0)) if video else 0
    height = int(video.get("height", 0)) if video else 0
    rotation = _rotation(video) if video else 0
    if rotation in (90, 270):
        width, height = height, width

    duration = float(fmt.get("duration") or 0)
    if kind == "video" and video and video.get("duration"):
        duration = float(video["duration"]) or duration

    return {
        "kind": kind,
        "duration": round(duration, 3) if kind != "image" else 0.0,
        "width": width,
        "height": height,
        "fps": _fps(video) if kind == "video" else 0,
        "has_audio": audio is not None,
        "video_codec": video.get("codec_name") if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "rotation": rotation,
        "creation_time": (fmt.get("tags") or {}).get("creation_time"),
    }


def _fps(stream) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = stream.get(key, "0/0")
        try:
            num, den = value.split("/")
            if float(den):
                return round(float(num) / float(den), 3)
        except (ValueError, ZeroDivisionError):
            continue
    return 30.0


def _rotation(stream) -> int:
    rot = (stream.get("tags") or {}).get("rotate")
    if rot is None:
        for side in stream.get("side_data_list", []) or []:
            if "rotation" in side:
                rot = side["rotation"]
    try:
        return abs(int(float(rot))) % 360
    except (TypeError, ValueError):
        return 0


_FLOAT = r"(-?\d+(?:\.\d+)?)"


def parse_float_lines(text: str, key: str):
    return [float(m) for m in re.findall(key + r"\s*[:=]\s*" + _FLOAT, text)]
