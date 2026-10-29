"""Check an edit plan against the real media and repair what can be repaired."""

from .plan import Clip, EditPlan, clip_length, timeline, transition_len

MIN_CLIP = 0.4


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def validate(plan: EditPlan, media: dict, analysis: dict | None = None):
    """Return (fixed_plan, issues). `media` maps id -> media record."""
    issues = []
    plan = plan.model_copy(deep=True)
    kept = []
    for i, clip in enumerate(plan.clips, 1):
        m = media.get(clip.media_id)
        if not m:
            issues.append(f"Clipul {i}: fișierul „{clip.media_id}” nu există — l-am scos.")
            continue
        if m["kind"] not in ("video", "image"):
            issues.append(f"Clipul {i}: {m['name']} nu e video sau imagine — l-am scos.")
            continue
        clip.speed = _clamp(clip.speed or 1.0, 0.25, 4.0)
        if m["kind"] == "image":
            length = _clamp(clip.end - clip.start if clip.end > clip.start else clip.end, 0.5, 15)
            clip.start, clip.end, clip.speed = 0.0, round(length, 3), 1.0
            clip.keep_audio = False
        else:
            dur = m["duration"]
            start = _clamp(clip.start, 0, max(0, dur - MIN_CLIP))
            end = _clamp(clip.end, start + MIN_CLIP, dur)
            if (start, end) != (clip.start, clip.end):
                issues.append(f"Clipul {i}: intervalul {clip.start:.1f}–{clip.end:.1f}s depășea "
                              f"fișierul ({dur:.1f}s) — ajustat la {start:.1f}–{end:.1f}s.")
            clip.start, clip.end = round(start, 3), round(end, 3)
            if not m.get("has_audio"):
                clip.keep_audio = False
        clip.volume = _clamp(clip.volume, 0, 2)
        clip.transition_duration = _clamp(clip.transition_duration, 0.15, 1.5)
        c = clip.color
        c.brightness = _clamp(c.brightness, -0.3, 0.3)
        c.contrast = _clamp(c.contrast, 0.6, 1.6)
        c.saturation = _clamp(c.saturation, 0, 2)
        c.warmth = _clamp(c.warmth, -1, 1)
        length = clip_length(clip)
        good = []
        for o in clip.overlays:
            o.text = " ".join(o.text.split())[:80]
            if not o.text:
                continue
            o.start = _clamp(o.start, 0, max(0, length - 0.3))
            o.duration = _clamp(o.duration, 0.3, length - o.start)
            good.append(o)
        clip.overlays = good
        kept.append(clip)
    plan.clips = kept
    if not kept:
        issues.append("Planul nu mai are niciun clip valid.")
        return plan, issues
    plan.clips[0].transition_in = "cut"

    if plan.tighten and analysis:
        from . import tighten
        plan, removed = tighten.apply(plan, media, analysis)
        if removed > 0.2:
            issues.append(f"Am scos {removed:.1f}s de pauze și ezitări (jump cuts).")


    if plan.music:
        m = media.get(plan.music.media_id)
        if not m or m["kind"] not in ("audio", "video") or (m["kind"] == "video" and not m.get("has_audio")):
            issues.append("Muzica aleasă nu e un fișier audio valid — am scos-o.")
            plan.music = None
        else:
            plan.music.start = _clamp(plan.music.start, 0, max(0, m["duration"] - 1))
            plan.music.volume = _clamp(plan.music.volume, 0, 1.5)

    if plan.fps not in (24, 25, 30, 50, 60):
        plan.fps = 30

    beat_info = ((analysis or {}).get(plan.music.media_id) or {}).get("beats") or {} if plan.music else {}
    if plan.snap_to_beat and plan.music and analysis:
        moved = snap_to_beats(plan, beat_info.get("beats") or [], media)
        if moved:
            issues.append(f"Am aliniat {moved} tăieturi pe ritmul muzicii.")
    if plan.music and plan.music.align_end:
        if align_music_end(plan, media[plan.music.media_id], beat_info):
            issues.append("Melodia se termină odată cu video-ul.")

    if plan.beat_fx_every not in (1, 2, 4):
        plan.beat_fx_every = 2
    if plan.beat_fx != "none" and not plan.music:
        plan.beat_fx = "none"

    total = timeline(plan)[-1]
    end = total[1] + total[2]
    plan.captions = [c for c in plan.captions if c.text.strip() and c.start < end]
    for c in plan.captions:
        c.start = _clamp(c.start, 0, end)
        c.end = _clamp(c.end, c.start + 0.3, end)
    plan.voiceover = sorted([v for v in plan.voiceover if v.text.strip() and 0 <= v.start < end],
                            key=lambda v: v.start)
    if plan.thumbnail and plan.thumbnail.media_id not in media:
        plan.thumbnail = None
    return plan, issues


def align_music_end(plan: EditPlan, song: dict, beat_info: dict) -> bool:
    """Choose the song's start so its ending lands on the video's ending. The shift is a whole
    number of beats away from the current start, so cuts already snapped stay on the beat."""
    from .plan import total_length
    total = total_length(plan)
    want = song["duration"] - total
    if want <= 0.5:
        return False
    start = want
    if beat_info.get("bpm"):
        period = 60.0 / beat_info["bpm"]
        k = round((want - plan.music.start) / period)
        start = plan.music.start + k * period
        if start < 0 or start > song["duration"] - total + period / 2:
            start = want
    plan.music.start = round(max(0.0, start), 3)
    plan.music.fade_out = min(plan.music.fade_out, 1.0)
    return True


def snap_to_beats(plan: EditPlan, beats, media) -> int:
    """Shift each clip's out-point so the cut lands on the nearest beat (within ±0.35 s)."""
    beats = [b - plan.music.start for b in beats if b >= plan.music.start]
    if len(beats) < 4:
        return 0
    moved = 0
    t = 0.0
    for i, clip in enumerate(plan.clips):
        nxt = plan.clips[i + 1] if i + 1 < len(plan.clips) else None
        length = clip_length(clip)
        cut = t + length
        target = min(beats, key=lambda b: abs(b - cut))
        delta = target - cut
        if nxt is not None and 0.02 < abs(delta) <= 0.35:
            new_end = clip.end + delta * clip.speed
            m = media[clip.media_id]
            limit = 15 if m["kind"] == "image" else m["duration"]
            if clip.start + MIN_CLIP <= new_end <= limit:
                clip.end = round(new_end, 3)
                length = clip_length(clip)
                moved += 1
        overlap = transition_len(clip, nxt) if nxt is not None else 0
        t += length - overlap
    return moved


def describe(plan: EditPlan) -> str:
    tl = timeline(plan)
    end = tl[-1][1] + tl[-1][2] if tl else 0
    return f"{len(plan.clips)} clipuri, {end:.1f}s, {plan.aspect}"


__all__ = ["validate", "snap_to_beats", "describe", "Clip"]
