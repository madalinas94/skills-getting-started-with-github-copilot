"""Long video → several vertical Shorts, each with a hook, captions and a virality score."""

import re
from typing import List

from pydantic import BaseModel, Field

from .plan import Clip, EditPlan, Music, Overlay, Thumbnail


class Moment(BaseModel):
    title: str = Field(description="Short working title, in the speaker's language")
    start: float = Field(description="Start in seconds in the long video, on a sentence boundary")
    end: float = Field(description="End in seconds; the clip must make sense on its own")
    hook: str = Field(description="On-screen hook for the first 2 seconds, max 6 words")
    score: int = Field(description="0-100: how likely this moment is to hold attention and be shared")
    why: str = Field(description="One sentence, in Romanian: why this moment works")
    caption: str = Field(description="Post caption for TikTok/Reels, in the speaker's language")
    hashtags: List[str] = Field(default_factory=list)


class Moments(BaseModel):
    moments: List[Moment]


def _sentences(segments):
    """Merge Whisper segments into sentence-sized units [start, end, text]."""
    out = []
    for s, e, text in segments:
        if out and not re.search(r"[.!?…]$", out[-1][2].strip()) and s - out[-1][1] < 1.0:
            out[-1] = [out[-1][0], e, out[-1][2] + " " + text]
        else:
            out.append([s, e, text])
    return out


def heuristic(speech: dict, count: int, min_len=20.0, max_len=55.0) -> List[Moment]:
    """No AI: windows of whole sentences, scored by speech density, questions/exclamations
    and how strong the first sentence is."""
    sents = _sentences(speech.get("segments") or [])
    if not sents:
        return []
    candidates = []
    for i in range(len(sents)):
        j = i
        while j + 1 < len(sents) and sents[j + 1][1] - sents[i][0] <= max_len:
            j += 1
        start, end = sents[i][0], sents[j][1]
        if end - start < min_len:
            continue
        text = " ".join(s[2] for s in sents[i:j + 1])
        words = len(text.split())
        density = words / (end - start)  # words per second
        punch = text.count("!") * 2 + text.count("?") * 1.5
        first = sents[i][2]
        hook_bonus = 6 if re.search(r"\?|!|\d", first) else 0
        score = min(99, int(30 + density * 12 + punch * 3 + hook_bonus))
        candidates.append((score, start, end, first))
    candidates.sort(reverse=True)
    chosen = []
    for score, start, end, first in candidates:
        if all(end <= c.start or start >= c.end for c in chosen):
            hook = " ".join(first.split()[:6]).rstrip(",;:")
            chosen.append(Moment(title=hook, start=round(start, 2), end=round(end, 2), hook=hook,
                                 score=score, why="Moment dens, cu fraze întregi și energie în voce.",
                                 caption=first, hashtags=["shorts", "romania"]))
        if len(chosen) >= count:
            break
    return sorted(chosen, key=lambda m: -m.score)


def to_plan(moment: Moment, media: dict, analysis: dict, music: dict | None = None,
            caption_style: str = "karaoke") -> EditPlan:
    """A ready-to-post vertical edit of one moment."""
    info = analysis.get(media["id"]) or {}
    wide = media["width"] >= media["height"]
    fit = "track" if wide and info.get("faces") else ("blur_bg" if wide else "fill")
    clip = Clip(media_id=media["id"], start=moment.start, end=moment.end, fit=fit, keep_audio=True,
                color=(info.get("auto_color") or {}),
                overlays=[Overlay(text=moment.hook, style="big_word", position="center", animation="pop",
                                  start=0.1, duration=2.0)],
                reason=moment.why)
    return EditPlan(
        title=moment.title, summary=moment.why, aspect="9:16", fps=30, clips=[clip],
        music=Music(media_id=music["id"], volume=0.12, duck=True, align_end=True) if music else None,
        caption_style=caption_style, tighten=True, voice_enhance=True, emphasis_zoom=True, sfx=True,
        thumbnail=Thumbnail(media_id=media["id"], time=moment.start + 1.0, text=moment.hook),
    )
