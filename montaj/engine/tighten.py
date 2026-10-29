"""Jump cuts: remove pauses, filler sounds and stumbles from clips with speech.

Works from the Whisper word timings when there are any, otherwise from the silences ffmpeg
detected. Every other piece gets a slight close-up so the cuts read as intentional, the way
talking-head creators edit.
"""

import re

from .plan import Clip, EditPlan

# sounds, not words; real words like "deci" or "gen" are left to the speaker
FILLERS = {"ă", "ăă", "ăăă", "â", "îî", "îm", "ââ", "eee", "ee", "hm", "hmm", "mm", "mmm", "mhm",
           "uh", "um", "uhm", "umm", "ah", "eh", "er", "erm", "ehm", "ăm", "aaa"}
MAX_PAUSE = 0.35      # longer gaps between words are cut
PAD_BEFORE = 0.06
PAD_AFTER = 0.12
MIN_PIECE = 0.35
MARK = "✂"  # pieces already tightened are not cut again


def _norm(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower())


def speech_ranges(words, start: float, end: float):
    """Ranges inside [start, end) worth keeping, from word timings."""
    kept = []  # (start, end, must_cut_before)
    prev = None
    cut_next = False
    removed_end = start
    for s, e, w in words:
        if e <= start or s >= end:
            continue
        n = _norm(w)
        if not n or n in FILLERS:
            cut_next = True  # a short "ăăă" still has to go, however short the gap
            if kept:  # padding must not reach into the filler
                kept[-1] = (kept[-1][0], min(kept[-1][1], s), kept[-1][2])
            removed_end = e
            continue
        if prev is not None and n == prev[1] and s - prev[0] < 1.0:
            dropped = kept.pop()  # stumble: "eu eu" → keep the second take
            removed_end = max(removed_end, dropped[1])
            cut_next = True
        kept.append((max(start, s - PAD_BEFORE, removed_end), min(end, e + PAD_AFTER), cut_next))
        prev = (e, n)
        cut_next = False
    merged = []
    for s, e, cut in kept:
        if merged and not cut and s - merged[-1][1] <= MAX_PAUSE:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return [(round(s, 3), round(e, 3)) for s, e in merged if e - s >= MIN_PIECE]


def sound_ranges(silences, start: float, end: float):
    """Fallback without a transcript: everything that isn't a detected silence."""
    out, t = [], start
    for s, e in sorted(silences):
        e = end if e is None else e
        if e <= start or s >= end:
            continue
        if s - t >= MIN_PIECE:
            out.append((round(t, 3), round(min(s + PAD_AFTER, end), 3)))
        t = max(t, e - PAD_BEFORE)
    if end - t >= MIN_PIECE:
        out.append((round(t, 3), round(end, 3)))
    return out


def _split(clip: Clip, ranges, alternate: bool):
    """Pieces of one clip; overlays and B-roll go to the piece that contains their start."""
    pieces = []
    for i, (s, e) in enumerate(ranges):
        p = clip.model_copy(deep=True)
        p.start, p.end = s, e
        p.overlays, p.broll = [], []
        p.reason = f"{MARK} {clip.reason}".strip()
        if i > 0:
            p.transition_in = "cut"
            if alternate and clip.motion == "none" and i % 2 == 1:
                p.motion = "close_up"
        pieces.append(p)

    def place(t_on_screen):
        """Map a time on the original clip's screen to (piece index, time inside it)."""
        src = clip.start + t_on_screen * clip.speed
        for i, (s, e) in enumerate(ranges):
            if src < e or i == len(ranges) - 1:
                return i, max(0.0, (max(src, s) - s) / clip.speed)
        return 0, 0.0

    for o in clip.overlays:
        i, t = place(o.start)
        pieces[i].overlays.append(o.model_copy(update={"start": round(t, 3)}))
    for b in clip.broll:
        i, t = place(b.at)
        pieces[i].broll.append(b.model_copy(update={"at": round(t, 3)}))
    return pieces


def apply(plan: EditPlan, media: dict, analysis: dict):
    """Return (plan, seconds_removed). Clips without their own sound are left alone."""
    out, removed = [], 0.0
    for clip in plan.clips:
        m = media.get(clip.media_id) or {}
        info = analysis.get(clip.media_id) or {}
        if not clip.keep_audio or m.get("kind") != "video" or clip.reason.startswith(MARK):
            out.append(clip)
            continue
        words = (info.get("speech") or {}).get("words")
        ranges = (speech_ranges(words, clip.start, clip.end) if words
                  else sound_ranges(info.get("silences") or [], clip.start, clip.end))
        if not ranges or (len(ranges) == 1 and ranges[0] == (clip.start, clip.end)):
            out.append(clip)
            continue
        removed += (clip.end - clip.start) - sum(e - s for s, e in ranges)
        out.extend(_split(clip, ranges, alternate=True))
    plan = plan.model_copy(update={"clips": out})
    return plan, round(removed, 2)


# Studio voice: rumble out, broadband noise down, presence up, sibilance tamed, evened out
VOICE_CHAIN = ["highpass=f=80", "afftdn=nf=-28:tn=1", "equalizer=f=200:t=q:w=1:g=-2",
               "equalizer=f=3200:t=q:w=1.2:g=3", "deesser=i=0.4",
               "acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=3", "alimiter=limit=0.95"]
