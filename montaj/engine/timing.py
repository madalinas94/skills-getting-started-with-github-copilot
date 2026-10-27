"""Everything the renderer needs besides the plan: word timings for captions, the beat grid
for beat effects, rendered voice-over lines and face tracks for the follow-the-face crop."""

from pathlib import Path

from . import ff, speech, tts
from .plan import EditPlan, timeline, total_length


def beat_grid(plan: EditPlan, analysis: dict):
    """{"period", "phase"} of the music's beats on the final timeline, or None."""
    if not plan.music:
        return None
    info = (analysis.get(plan.music.media_id) or {}).get("beats") or {}
    beats = info.get("beats") or []
    if not info.get("bpm") or len(beats) < 4:
        return None
    period = 60.0 / info["bpm"]
    phase = (beats[0] - plan.music.start) % period
    return {"period": round(period, 4), "phase": round(phase, 4)}


def clip_words(plan: EditPlan, analysis: dict):
    """Transcribed words of clips that keep their sound, mapped onto the final timeline."""
    out = []
    for clip, start, length in timeline(plan):
        if not clip.keep_audio:
            continue
        words = ((analysis.get(clip.media_id) or {}).get("speech") or {}).get("words") or []
        for s, e, w in words:
            if s < clip.start - 0.05 or s >= clip.end:
                continue
            ts = start + (s - clip.start) / clip.speed
            te = start + (min(e, clip.end) - clip.start) / clip.speed
            if ts < start + length:
                out.append([round(ts, 2), round(min(te, start + length), 2), w])
    return out


def voiceover(plan: EditPlan, workdir: Path, api_key: str | None, voice: str | None, step=None):
    """Synthesize every voice line; returns (tracks, words, issues). Lines never overlap."""
    tracks, words, issues = [], [], []
    if not plan.voiceover:
        return tracks, words, issues
    if not api_key:
        issues.append("Vocea off are nevoie de cheia ElevenLabs (Setări). Am randat fără voce.")
        return tracks, words, issues
    total = total_length(plan)
    cursor = 0.0
    for i, line in enumerate(plan.voiceover):
        if step:
            step(f"Generez vocea off ({i + 1}/{len(plan.voiceover)})")
        path = tts.synthesize(line.text, workdir / "tts", api_key, voice)
        duration = ff.probe(path)["duration"]
        start = max(line.start, cursor)
        if start >= total - 0.3:
            issues.append(f"Replica „{line.text[:40]}…” nu mai încape în video — am sărit-o.")
            continue
        tracks.append({"file": str(path), "start": round(start, 3), "duration": duration})
        if speech.available():
            words += [[round(start + s, 2), round(start + e, 2), w]
                      for s, e, w in speech.transcribe(path)["words"]]
        else:
            words += speech.words_even(line.text, start, duration)
        cursor = start + duration + 0.25
        if cursor > total + 0.5:
            issues.append("Vocea off e mai lungă decât video-ul; finalul ei se taie.")
    return tracks, words, issues


def prepare(plan: EditPlan, analysis: dict, workdir: Path, eleven_key=None, voice=None, step=None):
    """Build the render extras dict; returns (extras, issues)."""
    tracks, vo_words, issues = voiceover(plan, workdir, eleven_key, voice, step)
    words = sorted(clip_words(plan, analysis) + vo_words) if plan.caption_style != "none" else []
    faces = {}
    for clip in plan.clips:
        if clip.fit == "track":
            faces[clip.media_id] = (analysis.get(clip.media_id) or {}).get("faces") or []
    extras = {"beat": beat_grid(plan, analysis), "words": words, "voice": tracks, "faces": faces}
    if plan.caption_style != "none" and not words:
        if not speech.available():
            issues.append("Subtitrările automate au nevoie de Whisper (pip install faster-whisper).")
        else:
            issues.append("Nu am auzit vorbire în clipurile cu sunet păstrat, deci nu am pus subtitrări automate.")
    return extras, issues
