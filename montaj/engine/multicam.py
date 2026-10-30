"""Podcast / interview with 2-3 cameras: sync them by sound, cut to whoever is talking.

Each camera's own microphone hears its person loudest, so the active speaker is the camera
whose audio is loudest relative to its own normal level. All cameras then play the same
"master" sound (the best microphone), shifted into each camera's timing.
"""

import subprocess
from pathlib import Path

import numpy as np

from . import ff
from .plan import Clip, EditPlan

RATE = 8000
ENV_RATE = 100  # envelope samples per second
MIN_SHOT = 2.0


def _audio(path, seconds=None):
    args = [ff.binary("ffmpeg"), "-hide_banner", "-nostdin", "-v", "error"]
    if seconds:
        args += ["-t", str(seconds)]
    args += ["-i", str(path), "-vn", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"]
    raw = subprocess.run(args, capture_output=True).stdout
    return np.frombuffer(raw[: len(raw) // 2 * 2], np.int16).astype(np.float32) / 32768


def _envelope(a):
    hop = RATE // ENV_RATE
    n = len(a) // hop
    return np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-9)


def offsets(paths, seconds=240):
    """Offset of each recording relative to the first: camera k's time = first's time + offset_k."""
    envs = [_envelope(_audio(p, seconds)) for p in paths]
    ref = np.log(envs[0] + 1e-4)
    ref = ref - ref.mean()
    out = [0.0]
    for e in envs[1:]:
        x = np.log(e + 1e-4)
        x = x - x.mean()
        n = 1 << int(np.ceil(np.log2(len(ref) + len(x))))
        corr = np.fft.irfft(np.fft.rfft(ref, n) * np.conj(np.fft.rfft(x, n)), n)
        lag = int(np.argmax(corr))
        if lag > n // 2:
            lag -= n
        out.append(round(-lag / ENV_RATE, 3))
    return out


def speakers(paths, offs, duration, window=0.5):
    """Per-window index of the camera whose mic is relatively loudest (or -1 for silence)."""
    levels = []
    for p, off in zip(paths, offs):
        env = _envelope(_audio(p))
        db = 20 * np.log10(env + 1e-5)
        db = db - np.percentile(db, 20)  # relative to this mic's quiet baseline
        levels.append((db, off))
    steps = int(duration / window)
    out = []
    for i in range(steps):
        t = i * window
        vals = []
        for db, off in levels:
            a, b = int((t + off) * ENV_RATE), int((t + off + window) * ENV_RATE)
            vals.append(db[max(0, a):max(0, b)].mean() if 0 <= a < len(db) else -99)
        order = np.argsort(vals)[::-1]
        best = int(order[0])
        margin = vals[best] - (vals[order[1]] if len(vals) > 1 else -99)
        out.append(best if vals[best] > 4 and margin > 3 else -1)
    return out


def _shots(seq, window, n_cams, wide=None):
    """Turn per-window speakers into shots: min 2 s, hold through short silences."""
    shots, cur, start = [], None, 0.0
    for i, s in enumerate(seq + [None]):
        t = i * window
        if s == -1:
            continue
        if cur is None:
            cur, start = s, t
            continue
        if s != cur and t - start >= MIN_SHOT:
            shots.append([cur, start, t])
            cur, start = s, t
    if cur is not None:
        shots.append([cur, start, len(seq) * window])
    merged = []
    for s in shots:
        if merged and merged[-1][0] == s[0]:
            merged[-1][2] = s[2]
        else:
            merged.append(s)
    if wide is not None:  # breathe: a wide shot every ~20 s on long single-speaker stretches
        out = []
        for cam, a, b in merged:
            t = a
            while b - t > 22:
                out.append([cam, t, t + 18])
                out.append([wide, t + 18, t + 21])
                t += 21
            out.append([cam, t, b])
        merged = out
    return merged


def build_plan(cams: list, offs: list, duration: float, seq: list, window: float, layout: str,
               aspect: str, title: str, wide_index=None) -> EditPlan:
    """cams: media records (same order as offs)."""
    if layout == "split" and len(cams) >= 2:
        clip = Clip(media_id=cams[0]["id"], start=0.0, end=round(duration, 3), keep_audio=True,
                    split_with=cams[1]["id"], split_offset=round(offs[1] - offs[0], 3), fit="track",
                    reason="Split-screen: amândoi vorbitorii tot timpul")
        return EditPlan(title=title, summary="Podcast în split-screen, sincronizat după sunet.", aspect=aspect,
                        clips=[clip], caption_style="karaoke", voice_enhance=True)
    clips = []
    for cam, a, b in _shots(seq, window, len(cams), wide_index):
        if b - a < 0.5:
            continue
        m = cams[cam]
        clips.append(Clip(media_id=m["id"], start=round(a + offs[cam], 3), end=round(b + offs[cam], 3),
                          keep_audio=True, fit="track",
                          reason="Plan larg" if cam == wide_index else f"Vorbește persoana de pe camera {cam + 1}"))
    if not clips:
        clips = [Clip(media_id=cams[0]["id"], start=offs[0], end=offs[0] + duration, keep_audio=True)]
    return EditPlan(title=title, summary=f"Podcast cu {len(cams)} camere, schimbat automat pe cine vorbește.",
                    aspect=aspect, clips=clips, caption_style="karaoke", voice_enhance=True)


def aligned_master(master_path: Path, master_off: float, cam_off: float, dest: Path) -> Path:
    """The master microphone shifted into one camera's timing (so every cut sounds the same)."""
    if dest.exists():
        return dest
    shift = cam_off - master_off  # camera time t ↔ master time t - shift
    args = ["-i", master_path, "-vn", "-ac", "2", "-ar", "48000"]
    if shift > 0:
        ms = int(shift * 1000)
        args += ["-af", f"adelay={ms}|{ms}"]
    elif shift < 0:
        args = ["-ss", f"{-shift:.3f}"] + args
    ff.run([*args, dest])
    return dest
