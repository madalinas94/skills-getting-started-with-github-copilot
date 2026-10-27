"""Hand-off files for other editors: FCPXML (DaVinci Resolve, Final Cut), EDL, SRT, project JSON."""

from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from .plan import EditPlan, Overlay, clip_length, timeline
from .render import frame_size


def _t(seconds: float, fps: int) -> str:
    """Rational time snapped to whole frames, as FCPXML wants it ("123/30s")."""
    frames = round(seconds * fps)
    f = Fraction(frames, fps)
    return f"{f.numerator}/{f.denominator}s" if f.denominator != 1 else f"{f.numerator}s"


def _file_url(path: Path) -> str:
    return path.resolve().as_uri()


def fcpxml(plan: EditPlan, media: dict, media_dir: Path) -> str:
    """FCPXML 1.9. DaVinci Resolve: File → Import → Timeline. Cuts, transitions and titles
    come across; colour grades and speed changes are noted on each clip for re-doing there."""
    fps = plan.fps
    W, H = frame_size(plan.aspect, "1080p")
    used = []
    for c in plan.clips:
        if c.media_id not in used:
            used.append(c.media_id)
    if plan.music and plan.music.media_id not in used:
        used.append(plan.music.media_id)

    res = [f'<format id="r0" frameDuration="{_t(1 / fps, fps)}" '
           f'width="{W}" height="{H}"/>',
           '<effect id="rx" name="Cross Dissolve" uid="FxPlug:4731E73A-8DAC-4113-9A30-AE85B1761265"/>',
           '<effect id="rt" name="Basic Title" uid=".../Titles.localized/Bumper:Opener.localized/'
           'Basic Title.localized/Basic Title.moti"/>']
    for i, mid in enumerate(used, 1):
        m = media[mid]
        dur = m["duration"] if m["kind"] != "image" else 3600
        res.append(
            f'<asset id="a{i}" name={quoteattr(m["name"])} start="0s" duration="{_t(dur, fps)}" '
            f'hasVideo="{1 if m["kind"] != "audio" else 0}" hasAudio="{1 if m.get("has_audio") else 0}" '
            + ('format="r0"' if m["kind"] != "audio" else "") + f'><media-rep kind="original-media" src={quoteattr(_file_url(media_dir / m["file"]))}/>'
            f'</asset>')
    ref = {mid: f"a{i}" for i, mid in enumerate(used, 1)}

    spine = []
    tl = timeline(plan)
    for i, (clip, start, length) in enumerate(tl):
        m = media[clip.media_id]
        if i > 0 and clip.transition_in != "cut":
            prev_start, prev_len = tl[i - 1][1], tl[i - 1][2]
            overlap = prev_start + prev_len - start
            spine.append(f'<transition name="Cross Dissolve" offset="{_t(start, fps)}" '
                         f'duration="{_t(overlap, fps)}"><filter-video ref="rx" name="Cross Dissolve"/></transition>')
        note = []
        if abs(clip.speed - 1) > 1e-3:
            note.append(f"viteză {clip.speed:g}x")
        if clip.color.look != "none":
            note.append(f"look {clip.color.look}")
        src_in = clip.start if m["kind"] == "video" else 0
        # connected items are timed in the parent clip's source time
        titles = "".join(_title(o, fps, k, src_in) for k, o in enumerate(clip.overlays))
        spine.append(
            f'<asset-clip ref="{ref[clip.media_id]}" name={quoteattr(m["name"])} offset="{_t(start, fps)}" '
            f'start="{_t(src_in, fps)}" duration="{_t(length, fps)}"'
            + (f' audioRole="dialogue"' if clip.keep_audio else "")
            + ">"
            + (f"<note>{escape(', '.join(note))}</note>" if note else "")
            + ("" if clip.keep_audio or m["kind"] != "video" else '<adjust-volume amount="-96dB"/>')
            + titles + "</asset-clip>")

    total = tl[-1][1] + tl[-1][2] if tl else 0
    if plan.music and spine:
        mu = plan.music
        # connected clip on lane -1 under the first spine item
        first = spine.index(next(s for s in spine if s.startswith("<asset-clip")))
        first_in = plan.clips[0].start if media[plan.clips[0].media_id]["kind"] == "video" else 0
        music = (f'<asset-clip ref="{ref[mu.media_id]}" lane="-1" offset="{_t(first_in, fps)}" name="Muzică" '
                 f'start="{_t(mu.start, fps)}" duration="{_t(total, fps)}" audioRole="music"/>')
        spine[first] = spine[first].replace("</asset-clip>", music + "</asset-clip>", 1)

    return ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<!DOCTYPE fcpxml>\n<fcpxml version=\"1.9\">\n"
            "<resources>\n" + "\n".join(res) + "\n</resources>\n<library><event name=\"Montaj\">"
            f"<project name={quoteattr(plan.title)}><sequence format=\"r0\" duration=\"{_t(total, fps)}\" "
            "tcStart=\"0s\" tcFormat=\"NDF\" audioLayout=\"stereo\" audioRate=\"48k\"><spine>\n"
            + "\n".join(spine) + "\n</spine></sequence></project></event></library>\n</fcpxml>\n")


def _title(o: Overlay, fps: int, k: int, parent_in: float) -> str:
    return (f'<title ref="rt" lane="{k + 1}" offset="{_t(parent_in + o.start, fps)}" duration="{_t(o.duration, fps)}" '
            f'name={quoteattr(o.text[:40])}><text><text-style ref="ts{k}">{escape(o.text)}</text-style></text>'
            f'<text-style-def id="ts{k}"><text-style font="Helvetica" fontSize="72" fontColor="1 1 1 1" '
            f'alignment="center"/></text-style-def></title>')


def _tc(seconds: float, fps: int) -> str:
    frames = round(seconds * fps)
    f = frames % fps
    s = frames // fps
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}:{f:02d}"


def edl(plan: EditPlan, media: dict) -> str:
    """CMX3600 EDL for DaVinci Resolve, Premiere and most NLEs. Cuts only: transitions,
    titles and music travel in the FCPXML."""
    fps = plan.fps
    lines = [f"TITLE: {plan.title[:60]}", "FCM: NON-DROP FRAME", ""]
    tl = timeline(plan)
    for n, (clip, start, length) in enumerate(tl, 1):
        m = media[clip.media_id]
        src_in = clip.start if m["kind"] == "video" else 0
        src_out = src_in + length * clip.speed if m["kind"] == "video" else length
        reel = "AX"
        lines.append(f"{n:03d}  {reel:<8} {'AA/V' if clip.keep_audio else 'V   '}  C        "
                     f"{_tc(src_in, fps)} {_tc(src_out, fps)} {_tc(start, fps)} {_tc(start + length, fps)}")
        lines.append(f"* FROM CLIP NAME: {m['name']}")
        if abs(clip.speed - 1) > 1e-3:
            lines.append(f"M2   {reel:<8} {clip.speed * fps:05.1f}                {_tc(src_in, fps)}")
        lines.append("")
    return "\n".join(lines)


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(plan: EditPlan) -> str:
    """Captions + on-screen texts as subtitles (CapCut, YouTube, DaVinci can import SRT)."""
    items = [(c.start, c.end, c.text) for c in plan.captions]
    for clip, start, _length in timeline(plan):
        for o in clip.overlays:
            items.append((start + o.start, start + o.start + o.duration, o.text))
    items.sort()
    out = []
    for i, (s, e, text) in enumerate(items, 1):
        out.append(f"{i}\n{_srt_time(s)} --> {_srt_time(e)}\n{text}\n")
    return "\n".join(out)


__all__ = ["fcpxml", "edl", "srt", "clip_length"]


def post_text(copy) -> str:
    """postare.txt: ready-to-paste copy for each platform."""
    lines = ["HOOK-URI (prima frază / primul text pe ecran):"]
    lines += [f"  {i}. {h}" for i, h in enumerate(copy.hooks, 1)]
    lines += ["", f"TITLU YOUTUBE: {copy.youtube_title}", ""]
    for p in copy.posts:
        lines += [f"=== {p.platform} ===", p.caption, " ".join("#" + t.lstrip("#") for t in p.hashtags), ""]
    lines += [f"Când să postezi: {copy.best_time}"]
    return "\n".join(lines) + "\n"
