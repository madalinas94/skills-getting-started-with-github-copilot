"""Media analysis: key frames, scene cuts, silences, exposure/colour stats and music beats."""

import array
import re
import subprocess
from pathlib import Path

from . import ff, speech

try:
    from . import vision
except ImportError:  # numpy missing: quality checks and face tracking are skipped
    vision = None

FRAME_WIDTH = 512  # frames sent to the AI: small enough to be cheap, big enough to read


def frame_times(duration: float, count: int):
    """Evenly spaced timestamps, avoiding the very first/last frame."""
    if duration <= 0:
        return [0.0]
    count = max(1, count)
    step = duration / (count + 1)
    return [round(step * (i + 1), 2) for i in range(count)]


def extract_frame(src, t: float, dest, width=FRAME_WIDTH):
    ff.run(["-ss", f"{t:.3f}", "-i", src, "-frames:v", "1",
            "-vf", f"scale={width}:-2", "-q:v", "4", dest])


def extract_frames(media: dict, src: Path, out_dir: Path, count: int):
    """Extract `count` frames (one for a photo). Returns [{t, file}] relative to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    if media["kind"] == "image":
        name = f"{media['id']}_f0.jpg"
        ff.run(["-i", src, "-frames:v", "1", "-vf", f"scale='min({FRAME_WIDTH},iw)':-2",
                "-q:v", "4", out_dir / name])
        return [{"t": 0.0, "file": name}]
    if media["kind"] != "video":
        return []
    for i, t in enumerate(frame_times(media["duration"], count)):
        name = f"{media['id']}_f{i}.jpg"
        try:
            extract_frame(src, t, out_dir / name)
            frames.append({"t": t, "file": name})
        except ff.FFmpegError:
            continue
    return frames


def thumbnail(media: dict, src: Path, dest: Path):
    t = 0 if media["kind"] == "image" else min(1.0, media["duration"] / 3)
    ff.run(["-ss", f"{t:.3f}", "-i", src, "-frames:v", "1",
            "-vf", "scale=320:-2", "-q:v", "5", dest])


def _stderr_of(args) -> str:
    cmd = [ff.binary("ffmpeg"), "-hide_banner", "-nostdin", *map(str, args)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.stderr


def scenes(src, threshold=0.3, max_seconds=600):
    """Timestamps where the picture changes a lot (natural cut points)."""
    text = _stderr_of(["-t", str(max_seconds), "-i", src, "-an",
                       "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo",
                       "-f", "null", "-"])
    return [round(float(t), 2) for t in re.findall(r"pts_time:(\d+(?:\.\d+)?)", text)]


def silences(src, noise_db=-35, min_len=0.6, max_seconds=600):
    """[(start, end)] ranges of silence in the audio track."""
    text = _stderr_of(["-t", str(max_seconds), "-i", src, "-vn",
                       "-af", f"silencedetect=noise={noise_db}dB:d={min_len}", "-f", "null", "-"])
    starts = ff.parse_float_lines(text, "silence_start")
    ends = ff.parse_float_lines(text, "silence_end")
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        out.append((round(max(0.0, s), 2), round(e, 2) if e is not None else None))
    return out


def picture_stats(src, kind: str, duration: float):
    """Average luma (0-255), saturation and luma range, sampled at ~1 fps."""
    vf = "scale=160:-2,signalstats,metadata=print"
    args = ["-i", src, "-vf", vf, "-an", "-f", "null", "-"]
    if kind == "video":
        args = ["-t", str(min(duration, 120)), "-i", src,
                "-vf", "fps=1," + vf, "-an", "-f", "null", "-"]
    text = _stderr_of(args)

    def avg(key):
        vals = ff.parse_float_lines(text, r"lavfi\.signalstats\." + key)
        return round(sum(vals) / len(vals), 1) if vals else None

    return {"luma": avg("YAVG"), "luma_low": avg("YLOW"), "luma_high": avg("YHIGH"),
            "saturation": avg("SATAVG")}


def auto_color(stats: dict) -> dict:
    """Corrective grade from picture stats: lift dark footage, tame flat or garish colour."""
    color = {"brightness": 0.0, "contrast": 1.0, "saturation": 1.0}
    luma = stats.get("luma")
    if luma is not None:
        target = 118.0
        color["brightness"] = round(max(-0.15, min(0.15, (target - luma) / 255 * 0.8)), 3)
    low, high = stats.get("luma_low"), stats.get("luma_high")
    if low is not None and high is not None and high - low < 150:
        color["contrast"] = round(min(1.25, 1 + (150 - (high - low)) / 400), 3)
    sat = stats.get("saturation")
    if sat is not None:
        if sat < 25:
            color["saturation"] = 1.3
        elif sat < 40:
            color["saturation"] = 1.15
        elif sat > 75:
            color["saturation"] = 0.9
    return color


def beats(src, max_seconds=600):
    """Estimate tempo and beat times of a music track (energy-onset autocorrelation)."""
    rate, hop = 11025, 256
    cmd = [ff.binary("ffmpeg"), "-hide_banner", "-nostdin", "-t", str(max_seconds), "-i", str(src),
           "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) - len(raw) % 2])
    if len(samples) < rate * 4:
        return {"bpm": None, "beats": []}

    energy = []
    for i in range(0, len(samples) - hop, hop):
        chunk = samples[i:i + hop]
        energy.append(sum(abs(x) for x in chunk[::4]) / (hop / 4))
    onset = [max(0.0, energy[i] - energy[i - 1]) for i in range(1, len(energy))]
    onset.insert(0, 0.0)
    frame_sec = hop / rate

    best_lag, best_score = None, 0.0
    min_lag = int(60 / 180 / frame_sec)
    max_lag = int(60 / 70 / frame_sec)
    n = len(onset)
    for lag in range(min_lag, max_lag + 1):
        score = sum(onset[i] * onset[i - lag] for i in range(lag, n, 2))
        bpm = 60 / (lag * frame_sec)
        score *= 1.0 + 0.15 * (1 - abs(bpm - 120) / 60)  # mild preference for common tempos
        if score > best_score:
            best_lag, best_score = lag, score
    if not best_lag:
        return {"bpm": None, "beats": []}

    # Refine to a fractional period (integer lags drift by up to a beat per minute),
    # jointly with the phase, using a comb over the onset curve.
    def comb(period, phase):
        total, k = 0.0, 0
        while True:
            i = int(phase + k * period + 0.5)
            if i >= n:
                return total
            total += onset[i]
            k += 1

    best = (0.0, best_lag, 0)
    period = best_lag - 1.0
    while period <= best_lag + 1.0:
        for phase in range(int(period) + 1):
            s = comb(period, phase)
            if s > best[0]:
                best = (s, period, phase)
        period += 0.02
    _, period, phase = best
    times, k = [], 0
    while phase + k * period < n:
        times.append(round((phase + k * period) * frame_sec, 3))
        k += 1
    return {"bpm": round(60 / (period * frame_sec), 1), "beats": times}


def music_mood(src, bpm, max_seconds=600) -> dict:
    """Loudness and dynamics of a track, summarised as calm / medium / energetic."""
    text = _stderr_of(["-t", str(max_seconds), "-i", src, "-vn", "-af", "ebur128=framelog=quiet",
                       "-f", "null", "-"])
    lufs = ff.parse_float_lines(text, r"\bI")
    lra = ff.parse_float_lines(text, "LRA")
    loud = lufs[-1] if lufs else None
    score = 0
    if bpm:
        score += 1 if bpm >= 105 else 0
        score += 1 if bpm >= 125 else 0
    if loud is not None:
        score += 1 if loud > -12 else 0
    mood = ["calm", "medium", "energetic", "energetic"][score]
    return {"lufs": loud, "lra": lra[-1] if lra else None, "mood": mood}


def analyze(media: dict, src: Path, frames_dir: Path, frame_count: int, deep: bool = True,
            transcribe: bool = True) -> dict:
    """Everything the planner needs about one file."""
    info = {"frames": [], "scenes": [], "silences": [], "stats": {}, "beats": None}
    kind = media["kind"]
    if kind in ("video", "image"):
        info["frames"] = extract_frames(media, src, frames_dir, frame_count)
        info["stats"] = picture_stats(src, kind, media["duration"])
        info["auto_color"] = auto_color(info["stats"])
        if deep and vision is not None:
            q = vision.scan(src, media)
            info["quality"] = {"issues": q["issues"], "score": q["score"]}
            info["faces"] = q["faces"]
            info["face_ratio"] = q["face_ratio"]
    if kind == "video" and deep:
        info["scenes"] = scenes(src)
        if media["has_audio"]:
            info["silences"] = silences(src)
            if transcribe and speech.available():
                try:
                    info["speech"] = speech.transcribe(src)
                    info["speech"]["stressed"] = speech.stressed(src, info["speech"]["words"])
                except Exception as exc:  # model download blocked, corrupt audio, ...
                    info["speech_error"] = f"Whisper nu a putut transcrie: {exc}"[:300]
    if kind == "audio" and deep:
        info["beats"] = beats(src)
        info["mood"] = music_mood(src, info["beats"].get("bpm"))
    return info


def style_fingerprint(media: dict, info: dict) -> dict:
    """Measurable style of a reference ("example") video: pace, look, format."""
    duration = media.get("duration") or 0
    cuts = info.get("scenes") or []
    shots = len(cuts) + 1
    return {
        "duration": duration,
        "aspect": f"{media['width']}x{media['height']}",
        "shots": shots,
        "avg_shot_seconds": round(duration / shots, 2) if duration else None,
        "luma": (info.get("stats") or {}).get("luma"),
        "saturation": (info.get("stats") or {}).get("saturation"),
    }
