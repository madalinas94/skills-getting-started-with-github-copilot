"""Rule-based planner: a decent first cut with no AI (and the fallback when there's no API key)."""

import re

from . import presets
from .plan import Caption, Clip, Color, EditPlan, Music, Overlay, Thumbnail, VoiceLine


def _shots(duration: float, cuts):
    """Split a video into shots at scene cuts; [(start, end)]."""
    points = [0.0] + [c for c in cuts if 0.3 < c < duration - 0.3] + [duration]
    return [(a, b) for a, b in zip(points, points[1:]) if b - a >= 0.6]


def _silent(t0, t1, silences):
    """Fraction of [t0, t1] that is silent."""
    total = 0.0
    for s, e in silences:
        e = t1 if e is None else e
        total += max(0.0, min(t1, e) - max(t0, s))
    return total / max(t1 - t0, 1e-6)


def _bad(t0, t1, issues):
    """Fraction of [t0, t1] inside a shaky / blurry / dark range."""
    total = 0.0
    for it in issues:
        total += max(0.0, min(t1, it["end"]) - max(t0, it["start"]))
    return total / max(t1 - t0, 1e-6)


def pick_music(audio: list, analysis: dict, pace: float, wanted_id=None):
    """The track whose energy fits the edit: fast pace → energetic, slow → calm."""
    if not audio:
        return None
    chosen = next((m for m in audio if m["id"] == wanted_id), None)
    if chosen:
        return chosen
    want = "energetic" if pace < 2.5 else "calm" if pace > 3.2 else "medium"
    rank = {"calm": 0, "medium": 1, "energetic": 2}

    def score(m):
        mood = ((analysis.get(m["id"]) or {}).get("mood") or {}).get("mood", "medium")
        return abs(rank[mood] - rank[want])
    return min(audio, key=score)


def split_script(text: str, total: float):
    """User-written voice-over script → lines spread over the edit."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if not sentences:
        return []
    step = max(1.0, (total - 0.5) / len(sentences))
    return [VoiceLine(start=round(0.4 + i * step, 2), text=s) for i, s in enumerate(sentences)]


def _sort_key(m):
    return (m.get("creation_time") or "", m["name"].lower())


def build(media: list, analysis: dict, settings: dict, style: dict | None = None) -> EditPlan:
    """media: material records (role == 'material'), analysis: id -> analyze() output.
    style: a preset or saved style (styles.resolve); defaults to the settings' preset."""
    style = style or presets.get(settings.get("preset"))
    aspect = settings.get("aspect") or style["aspect"]
    target = float(settings.get("duration") or style["duration"])
    pace = style["pace"]
    use_color = settings.get("auto_color", True)
    transitions = style["transitions"]
    motions = style["motions"]

    visuals = sorted([m for m in media if m["kind"] in ("video", "image")], key=_sort_key)
    audio = [m for m in media if m["kind"] == "audio"]
    music_media = pick_music(audio, analysis, pace, settings.get("music_id"))

    videos = [m for m in visuals if m["kind"] == "video"]
    photos = [m for m in visuals if m["kind"] == "image"]
    photo_len = max(1.6, min(3.5, pace * 1.2))
    video_budget = max(0.0, target - photo_len * len(photos))
    total_video = sum(m["duration"] for m in videos) or 1.0

    picks = {}  # media id -> list of (start, end)
    for m in videos:
        info = analysis.get(m["id"], {})
        share = max(pace, video_budget * m["duration"] / total_video)
        n = max(1, round(share / pace))
        shots = _shots(m["duration"], info.get("scenes") or [])
        sil = info.get("silences") or []
        bad = (info.get("quality") or {}).get("issues") or []
        if not shots:
            shots = [(0.0, m["duration"])]
        if len(shots) < n:  # long takes: split them so each pick comes from its own window
            split = []
            for a, b in shots:
                parts = max(1, round(n * (b - a) / m["duration"]))
                step = (b - a) / parts
                split += [(a + j * step, a + (j + 1) * step) for j in range(parts)]
            shots = split
        chosen = []
        # spread the picks over the shots, preferring the least silent part of each
        for k in range(n):
            a, b = shots[int(k * len(shots) / n)]
            seg = min(pace * (1.6 if style.get("keep_audio") else 1.0), b - a)
            if seg < 0.5:
                continue
            best, best_score = a, 9.0
            steps = max(1, int((b - a - seg) / 0.5))
            for s in range(steps + 1):
                t0 = a + 0.25 + s * 0.5 if b - a - seg > 0.5 else a
                t0 = min(t0, b - seg)
                score = _silent(t0, t0 + seg, sil) if style.get("keep_audio") else abs((t0 + seg / 2) - (a + b) / 2) / max(b - a, 1)
                score += 3 * _bad(t0, t0 + seg, bad)  # avoid shaky / blurry / dark moments
                if score < best_score:
                    best, best_score = t0, score
            chosen.append((round(best, 2), round(best + seg, 2)))
        picks[m["id"]] = sorted(set(chosen))

    clips = []
    for m in visuals:
        info = analysis.get(m["id"], {})
        color = Color(**(info.get("auto_color") if use_color and info.get("auto_color") else {}))
        for k, v in (style.get("color") or {}).items():  # saved styles carry their grade
            if k != "brightness" or not use_color:
                setattr(color, k, v)
        color.look = style["look"]
        color.vignette = bool(style.get("vignette"))
        wide = m["width"] >= m["height"]
        want_wide = aspect in ("16:9",)
        fit = style["fit"] if wide != want_wide else "fill"
        if fit == "fill" and wide != want_wide and (info.get("face_ratio") or 0) > 0.3:
            fit = "track"
        if m["kind"] == "image":
            clips.append(Clip(media_id=m["id"], start=0, end=photo_len, fit=fit,
                              motion=motions[len(clips) % len(motions)] if motions != ["none"] else "zoom_in",
                              color=color, keep_audio=False, reason="Fotografie cu mișcare Ken Burns"))
        else:
            for s, e in picks.get(m["id"], []):
                clips.append(Clip(media_id=m["id"], start=s, end=e, fit=fit,
                                  motion=motions[len(clips) % len(motions)],
                                  color=color.model_copy(),
                                  keep_audio=bool(style.get("keep_audio")) and m["has_audio"],
                                  reason="Cel mai bun moment din scenă (fără pauze)" if style.get("keep_audio")
                                  else "Mijlocul scenei, cadrul cel mai stabil"))

    for i, c in enumerate(clips):
        c.transition_in = "cut" if i == 0 else transitions[i % len(transitions)]
        c.transition_duration = 0.5 if c.transition_in in ("dissolve", "fadeblack", "fade", "fadewhite") else 0.3

    anims = style.get("animations") or ["fade"]
    title = (settings.get("title") or "").strip()
    if clips and title:
        clips[0].overlays.append(Overlay(text=title, start=0.2, duration=min(2.5, (clips[0].end - clips[0].start) - 0.3),
                                         style="title" if style["pace"] >= 3 else "big_word", position="center",
                                         animation=anims[0]))
    outro = (settings.get("outro") or "").strip()
    if clips and outro:
        last = clips[-1]
        length = (last.end - last.start) / last.speed
        last.overlays.append(Overlay(text=outro, start=max(0, length - 2), duration=min(2, length),
                                     style="caption", position="bottom", animation=anims[-1]))

    music = None
    if music_media:
        music = Music(media_id=music_media["id"],
                      volume=style.get("music_volume") or (0.35 if style.get("keep_audio") else 0.9),
                      duck=bool(style.get("keep_audio")) or bool(settings.get("voiceover_text")),
                      align_end=settings.get("music_align", True))

    thumb = None
    first_video = next((c for c in clips if media_by_id(media, c.media_id)["kind"] == "video"), None)
    if first_video:
        thumb = Thumbnail(media_id=first_video.media_id, time=(first_video.start + first_video.end) / 2,
                          text=title)

    notes = []
    available = sum(m["duration"] for m in videos) + photo_len * len(photos)
    if visuals and available < target * 0.8:
        notes.append(f"Ai material pentru ~{available:.0f}s, mai puțin decât ținta de {target:.0f}s. "
                     "Mai adaugă clipuri sau poze.")
    if not visuals:
        notes.append("Nu ai încărcat niciun video sau poză.")
    if not music_media:
        notes.append("Adaugă o melodie (MP3) ca să pot tăia pe ritm.")
    notes.append("Plan făcut automat, fără AI. Adaugă cheia API Anthropic pentru un montaj gândit cadru cu cadru.")

    plan = EditPlan(title=title or "Montaj nou", summary=f"Montaj automat în stilul „{style['label']}”, "
                    f"{len(clips)} cadre, ordonate cronologic.", aspect=aspect, fps=30, clips=clips,
                    music=music, captions=[], thumbnail=thumb, snap_to_beat=bool(music_media), notes=notes,
                    caption_style=settings.get("caption_style") or style.get("captions", "none"),
                    beat_fx=(settings.get("beat_fx") or style.get("beat_fx", "none")) if music_media else "none",
                    beat_fx_every=style.get("beat_every", 2))
    apply_switches(plan, settings, media, analysis)
    if settings.get("voiceover_text"):
        from .plan import total_length
        plan.voiceover = split_script(settings["voiceover_text"], total_length(plan))
    return plan


def apply_switches(plan: EditPlan, settings: dict, media: list, analysis: dict):
    """The user's on/off switches always win, whoever made the plan."""
    from .plan import Broll, clip_length
    for key in ("tighten", "voice_enhance", "emphasis_zoom", "sfx", "emoji"):
        if settings.get(key):
            setattr(plan, key, True)
    if settings.get("background") in ("portrait",):
        for c in plan.clips:
            if (analysis.get(c.media_id) or {}).get("faces") and c.background == "none":
                c.background = "portrait"
    if settings.get("auto_broll") and settings.get("stock_broll") and not any(c.broll for c in plan.clips):
        # cut away to free stock footage of what is being said ("stock:<query>" is downloaded later)
        from .stock import queries_from_words
        for c in plan.clips:
            if not c.keep_audio or clip_length(c) < 4:
                continue
            words = [w for w in ((analysis.get(c.media_id) or {}).get("speech") or {}).get("words") or []
                     if c.start <= w[0] < c.end]
            t = 2.0
            while t + 1.8 < clip_length(c):
                window = [w for w in words if c.start + t * c.speed - 2 <= w[0] < c.start + t * c.speed + 2]
                q = queries_from_words(window, 1)
                if q:
                    c.broll.append(Broll(media_id=f"stock:{q[0]}", at=round(t, 2), duration=1.8))
                t += 5.0
    if settings.get("auto_broll") and not any(c.broll for c in plan.clips):
        # no AI to match words to pictures: cut away every ~5 s of talking to other material
        others = [m for m in media if m["kind"] in ("video", "image")]
        k = 0
        for c in plan.clips:
            if not c.keep_audio or clip_length(c) < 5:
                continue
            pool = [m for m in others if m["id"] != c.media_id]
            t = 2.5
            while pool and t + 1.8 < clip_length(c):
                b = pool[k % len(pool)]
                c.broll.append(Broll(media_id=b["id"], at=round(t, 2), duration=1.8,
                                     source_start=round(b["duration"] / 3, 2) if b["kind"] == "video" else 0))
                k += 1
                t += 5.0
    return plan


def media_by_id(media, mid):
    return next(m for m in media if m["id"] == mid)


__all__ = ["build", "Caption"]
