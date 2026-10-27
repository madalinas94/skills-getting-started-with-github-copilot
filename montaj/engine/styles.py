"""Saved styles: the measurable "how" of an edit the user liked, reusable with one click.

A style has the same keys as a preset (see presets.py), so the automatic planner and the AI
brief treat built-in presets and saved styles the same way.
"""

import json
import time
import uuid
from collections import Counter
from pathlib import Path

from . import presets
from .plan import EditPlan, clip_length


def _top(values, n=4, default=None):
    c = Counter(v for v in values if v is not None)
    return [v for v, _ in c.most_common(n)] or (default or [])


def derive(plan: EditPlan, name: str) -> dict:
    """Turn a finished plan into a reusable style."""
    clips = plan.clips
    lengths = [clip_length(c) for c in clips] or [3.0]
    overlays = [o for c in clips for o in c.overlays]
    looks = _top([c.color.look for c in clips], 1, ["none"])
    order = [c.transition_in for c in clips[1:]] or ["cut"]
    return {
        "id": "s" + uuid.uuid4().hex[:8],
        "name": name or plan.title,
        "created": time.time(),
        "label": name or plan.title,
        "aspect": plan.aspect,
        "duration": round(sum(lengths)),
        "pace": round(sum(lengths) / len(lengths), 2),
        "transitions": order[:8],
        "look": looks[0],
        "vignette": sum(c.color.vignette for c in clips) > len(clips) / 2,
        "fit": _top([c.fit for c in clips], 1, ["fill"])[0],
        "keep_audio": sum(c.keep_audio for c in clips) > len(clips) / 2,
        "motions": _top([c.motion for c in clips], 4, ["none"]),
        "animations": _top([o.animation for o in overlays], 2, ["fade"]),
        "text_styles": _top([o.style for o in overlays], 3, []),
        "captions": plan.caption_style,
        "beat_fx": plan.beat_fx,
        "beat_every": plan.beat_fx_every,
        "music_volume": plan.music.volume if plan.music else None,
        "color": {
            "brightness": round(sum(c.color.brightness for c in clips) / len(clips), 3),
            "contrast": round(sum(c.color.contrast for c in clips) / len(clips), 3),
            "saturation": round(sum(c.color.saturation for c in clips) / len(clips), 3),
            "warmth": round(sum(c.color.warmth for c in clips) / len(clips), 3),
        },
        "brief": f"Stil salvat din „{plan.title}”: cadre de ~{sum(lengths) / len(lengths):.1f}s, "
                 f"look {looks[0]}, tranziții {', '.join(_top(order, 3))}, text {', '.join(_top([o.animation for o in overlays], 2, ['fade']))}.",
    }


class Library:
    def __init__(self, path: Path):
        self.path = path

    def all(self) -> list:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, items):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    def add(self, style: dict) -> dict:
        items = self.all()
        items.insert(0, style)
        self._save(items)
        return style

    def delete(self, sid: str):
        self._save([s for s in self.all() if s["id"] != sid])

    def get(self, sid: str):
        return next((s for s in self.all() if s["id"] == sid), None)


def resolve(settings: dict, library: Library | None) -> dict:
    """The effective style for a project: a saved style if chosen, else the preset."""
    sid = settings.get("style_id")
    if sid and library:
        saved = library.get(sid)
        if saved:
            return {**presets.get(saved.get("base_preset") or settings.get("preset")), **saved}
    return presets.get(settings.get("preset"))
