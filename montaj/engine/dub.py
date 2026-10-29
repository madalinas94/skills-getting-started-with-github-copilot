"""Dubbing: the same edit in other languages, spoken in the user's own (cloned) voice.

Steps: speech units from the transcript → translation (Claude, timed to fit) → ElevenLabs
speech per unit in the cloned voice → each line stretched to its slot → original speech
removed (Demucs stems when installed, otherwise ducked) → translated captions and on-screen text.
"""

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

import httpx2
from pydantic import BaseModel, Field

from . import ff, speech, tts
from .plan import EditPlan, timeline

LANGUAGES = {
    "en": "English", "fr": "Français", "it": "Italiano", "es": "Español", "de": "Deutsch",
    "pt": "Português", "nl": "Nederlands", "pl": "Polski", "hu": "Magyar", "el": "Ελληνικά",
    "tr": "Türkçe", "ru": "Русский", "uk": "Українська", "ar": "العربية", "hi": "हिन्दी",
    "ja": "日本語", "ko": "한국어", "zh": "中文", "ro": "Română",
}
MAX_TEMPO = 1.3


class Line(BaseModel):
    id: int
    text: str = Field(description="Translation, natural and spoken, about as long to say as the original")


class Translation(BaseModel):
    lines: List[Line]
    overlays: List[Line] = Field(default_factory=list, description="On-screen texts, same ids as given")
    title: str


def units(plan: EditPlan, analysis: dict):
    """Speech on the final timeline, grouped into sentences: [{id, start, end, text}]."""
    from .timing import clip_words
    words = clip_words(plan, analysis)
    out, cur = [], []
    for w in words:
        if cur and (w[0] - cur[-1][1] > 0.7 or re.search(r"[.!?…]$", cur[-1][2])):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return [{"id": i, "start": u[0][0], "end": u[-1][1], "text": " ".join(w[2] for w in u)}
            for i, u in enumerate(out)]


def overlay_texts(plan: EditPlan):
    texts = []
    for ci, clip in enumerate(plan.clips):
        for oi, o in enumerate(clip.overlays):
            texts.append({"id": ci * 100 + oi, "text": o.text})
    return texts


def apply_translation(plan: EditPlan, tr: Translation) -> EditPlan:
    """Copy of the plan with translated on-screen text and title (speech goes in separately)."""
    out = plan.model_copy(deep=True)
    by_id = {line.id: line.text for line in tr.overlays}
    for ci, clip in enumerate(out.clips):
        for oi, o in enumerate(clip.overlays):
            o.text = by_id.get(ci * 100 + oi, o.text)
    out.title = tr.title or out.title
    return out


# ----------------------------------------------------------------- voice clone (ElevenLabs)

def voice_sample(sources, dest: Path, max_seconds=90) -> Path:
    """Concatenate up to 90 s of clean speech: sources = [(path, [[start, end, text], ...])]."""
    parts, total = [], 0.0
    for path, segments in sources:
        for s, e, _t in segments:
            if total >= max_seconds:
                break
            d = min(e - s, max_seconds - total)
            if d >= 1.0:
                parts.append((path, s, d))
                total += d
    if total < 10:
        raise RuntimeError("Am nevoie de cel puțin 10 secunde în care vorbești, ca să-ți clonez vocea.")
    args, labels = [], []
    for k, (path, s, d) in enumerate(parts):
        args += ["-ss", f"{s:.2f}", "-t", f"{d:.2f}", "-i", str(path)]
        labels.append(f"[{k}:a]")
    fc = "".join(labels) + f"concat=n={len(parts)}:v=0:a=1,highpass=f=70,afftdn=nf=-25[a]"
    ff.run([*args, "-filter_complex", fc, "-map", "[a]", "-ac", "1", "-ar", "44100", "-b:a", "192k", dest])
    return dest


def clone_voice(sample: Path, name: str, api_key: str) -> str:
    """Instant voice clone; returns the new voice_id."""
    try:
        with sample.open("rb") as f:
            r = httpx2.post("https://api.elevenlabs.io/v1/voices/add",
                            headers={"xi-api-key": api_key},
                            data={"name": name, "description": "Vocea mea (Montaj)",
                                  "remove_background_noise": "true"},
                            files={"files": (sample.name, f, "audio/mpeg")}, timeout=180)
    except httpx2.HTTPError as exc:
        raise tts.TTSError(f"Nu mă pot conecta la ElevenLabs: {exc}") from exc
    if r.status_code >= 400:
        raise tts.TTSError(f"ElevenLabs nu a putut clona vocea ({r.status_code}): {r.text[:200]}")
    return r.json()["voice_id"]


# ----------------------------------------------------------------- separating speech from the rest

def demucs_available() -> bool:
    try:
        import demucs  # noqa: F401
        return True
    except ImportError:
        return False


def music_stem(src: Path, cache: Path) -> Path | None:
    """Everything except the voice (Demucs two-stem split), cached per source file."""
    if not demucs_available():
        return None
    key = hashlib.sha1(str(src.resolve()).encode()).hexdigest()[:12]
    dest = cache / f"bg_{key}.wav"
    if dest.exists():
        return dest
    work = cache / f"demucs_{key}"
    wav = work / "in.wav"
    work.mkdir(parents=True, exist_ok=True)
    ff.run(["-i", src, "-vn", "-ac", "2", "-ar", "44100", wav])
    proc = subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs",
                           "-o", str(work), str(wav)], capture_output=True, text=True)
    found = list(work.glob("**/no_vocals.wav"))
    if proc.returncode != 0 or not found:
        return None
    shutil.move(str(found[0]), dest)
    shutil.rmtree(work, ignore_errors=True)
    return dest


# ----------------------------------------------------------------- one language

def build(plan: EditPlan, speech_units: list, tr: Translation, workdir: Path, api_key: str | None,
          voice_id: str | None, media: dict, media_dir: Path, step=None, subtitles_only=False,
          lang_name: str = ""):
    """Returns (translated_plan, extras_override, issues) for one language."""
    issues = []
    out = apply_translation(plan, tr)
    texts = {line.id: line.text for line in tr.lines}
    if subtitles_only:  # original voice, translated captions
        from .plan import Caption
        out.captions = [Caption(start=u["start"], end=max(u["end"], u["start"] + 0.8), text=texts.get(u["id"], u["text"]))
                        for u in speech_units]
        out.caption_style = "none"
        return out, {"words": []}, issues
    if not api_key:
        raise tts.TTSError("Dublajul cu voce are nevoie de cheia ElevenLabs (Setări). "
                           "Poți alege „doar subtitrări traduse”.")
    tracks, words = [], []
    for k, u in enumerate(speech_units):
        text = texts.get(u["id"])
        if not text:
            continue
        if step:
            step(f"Vocea în {lang_name}: replica {k + 1}/{len(speech_units)}")
        path = tts.synthesize(text, workdir / "tts", api_key, voice_id)
        dur = ff.probe(path)["duration"]
        nxt = speech_units[k + 1]["start"] if k + 1 < len(speech_units) else u["end"] + 1.5
        slot = max(0.5, nxt - u["start"] - 0.05)
        tempo = 1.0
        if dur > slot:
            tempo = min(MAX_TEMPO, dur / slot)
            if dur / tempo > slot + 0.3:
                issues.append(f"Replica {k + 1} e mai lungă decât originalul; se suprapune puțin cu următoarea.")
        said = dur / tempo
        tracks.append({"file": str(path), "start": u["start"], "duration": said, "tempo": round(tempo, 3)})
        words += speech.words_even(text, u["start"], said)
    stems = {}
    for clip in plan.clips:
        m = media.get(clip.media_id)
        if clip.keep_audio and m and m["kind"] == "video" and clip.media_id not in stems:
            stem = music_stem(media_dir / m["file"], workdir / "stems")
            if stem:
                stems[clip.media_id] = stem
    extras = {"voice": tracks, "words": words}
    if stems:
        extras["bg_audio"] = stems
    else:
        extras["mute"] = [[u["start"] - 0.05, u["end"] + 0.1] for u in speech_units]
        issues.append("Fără Demucs, vocea originală e doar coborâtă sub dublaj. "
                      "Pentru separare curată: pip install demucs.")
    return out, extras, issues


__all__ = ["LANGUAGES", "Translation", "units", "build", "clone_voice", "voice_sample", "timeline"]
