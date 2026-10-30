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


SFX_DIR = Path(__file__).resolve().parent.parent / "assets" / "sfx"


def stressed_words(plan: EditPlan, analysis: dict) -> set:
    out = set()
    for clip in plan.clips:
        sp = (analysis.get(clip.media_id) or {}).get("speech") or {}
        words = sp.get("words") or []
        out |= {words[i][2] for i in sp.get("stressed") or [] if i < len(words)}
    return out


def emphasis_moments(plan: EditPlan, analysis: dict):
    """Timeline [start, end] of stressed words in clips that keep their sound."""
    out = []
    for clip, start, length in timeline(plan):
        if not clip.keep_audio:
            continue
        sp = (analysis.get(clip.media_id) or {}).get("speech") or {}
        words = sp.get("words") or []
        for i in sp.get("stressed") or []:
            if i >= len(words):
                continue
            s, e, _w = words[i]
            if clip.start <= s < clip.end:
                ts = start + (s - clip.start) / clip.speed
                te = min(start + length, ts + max(0.9, (e - s) / clip.speed + 0.5))
                if not out or ts - out[-1][1] > 1.5:
                    out.append([round(ts, 3), round(te, 3)])
    return out


def sfx_cues(plan: EditPlan):
    """Whoosh on transitions, boom on big words, pop when other text appears, riser before the end."""
    cues = []
    tl = timeline(plan)
    for i, (clip, start, length) in enumerate(tl):
        if i > 0 and clip.transition_in != "cut":
            cues.append({"file": str(SFX_DIR / "whoosh.wav"), "start": start - 0.15, "volume": 0.45})
        for o in clip.overlays:
            kind = "boom" if o.style in ("big_word", "title") else "pop"
            cues.append({"file": str(SFX_DIR / f"{kind}.wav"), "start": start + o.start,
                         "volume": 0.5 if kind == "boom" else 0.4})
    if tl and plan.music is None and len(tl) > 3:
        end = tl[-1][1] + tl[-1][2]
        cues.append({"file": str(SFX_DIR / "riser.wav"), "start": max(0, end - 1.4), "volume": 0.3})
    cues.sort(key=lambda c: c["start"])
    spaced = []
    for c in cues:  # never two effects on top of each other
        if c["start"] >= 0 and (not spaced or c["start"] - spaced[-1]["start"] >= 0.4):
            spaced.append(c)
    return spaced


def person_masks(plan: EditPlan, media: dict, media_dir: Path, workdir: Path, step=None):
    """Person masks for clips with a portrait / replaced background. Returns (masks, issues)."""
    from . import people
    from .render import mask_key
    need = [c for c in plan.clips if c.background != "none"]
    if not need:
        return {}, []
    if not people.available():
        return {}, ["Decuparea fundalului are nevoie de MediaPipe (pip install mediapipe)."]
    masks = {}
    for i, clip in enumerate(need):
        m = media[clip.media_id]
        if step:
            step(f"Decupez persoana din {m['name']} ({i + 1}/{len(need)})")
        key = mask_key(clip).replace(":", "_")
        dest = workdir / "masks" / f"{key}.mkv"
        dest.parent.mkdir(parents=True, exist_ok=True)
        masks[mask_key(clip)] = people.mask_video(media_dir / m["file"], m, clip.start, clip.end - clip.start, dest)
    return masks, []


def skin_masks(plan: EditPlan, media: dict, media_dir: Path, workdir: Path, step=None):
    """Facial-skin masks for clips with the beauty filter on."""
    from . import people
    from .render import mask_key
    need = [c for c in plan.clips if c.beauty > 0.01]
    if not need:
        return {}, []
    if not people.available():
        return {}, ["Filtrul beauty are nevoie de MediaPipe (pip install mediapipe)."]
    out = {}
    for i, clip in enumerate(need):
        m = media[clip.media_id]
        if step:
            step(f"Filtru beauty: găsesc fața în {m['name']} ({i + 1}/{len(need)})")
        dest = workdir / "masks" / f"skin_{mask_key(clip).replace(':', '_')}.mkv"
        dest.parent.mkdir(parents=True, exist_ok=True)
        out[mask_key(clip)] = people.skin_mask_video(media_dir / m["file"], m, clip.start, clip.end - clip.start, dest)
    return out, []


def prepare(plan: EditPlan, analysis: dict, workdir: Path, eleven_key=None, voice=None, step=None,
            media: dict | None = None, media_dir: Path | None = None):
    """Build the render extras dict; returns (extras, issues)."""
    tracks, vo_words, issues = voiceover(plan, workdir, eleven_key, voice, step)
    words = sorted(clip_words(plan, analysis) + vo_words) if plan.caption_style != "none" else []
    faces = {}
    for clip in plan.clips:
        if clip.fit == "track":
            faces[clip.media_id] = (analysis.get(clip.media_id) or {}).get("faces") or []
    extras = {"beat": beat_grid(plan, analysis), "words": words, "voice": tracks, "faces": faces}
    if plan.emphasis_zoom:
        extras["emphasis"] = emphasis_moments(plan, analysis)
    extras["key_words"] = stressed_words(plan, analysis)
    if plan.sfx:
        extras["sfx"] = sfx_cues(plan)
    extras["faces_all"] = {mid: (info or {}).get("faces") or [] for mid, info in analysis.items()}
    if media is not None and media_dir is not None:
        masks, more = person_masks(plan, media, media_dir, workdir, step)
        extras["masks"] = masks
        issues += more
        skins, more = skin_masks(plan, media, media_dir, workdir, step)
        extras["skins"] = skins
        issues += more
    if plan.caption_style != "none" and not words:
        if not speech.available():
            issues.append("Subtitrările automate au nevoie de Whisper (pip install faster-whisper).")
        else:
            issues.append("Nu am auzit vorbire în clipurile cu sunet păstrat, deci nu am pus subtitrări automate.")
    return extras, issues
