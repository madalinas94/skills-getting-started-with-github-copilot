"""The AI editor: Claude looks at the frames, reads the rules and returns an EditPlan."""

import base64
import json
from pathlib import Path

import anthropic

from . import presets
from .plan import EditPlan

MODELS = {
    "claude-sonnet-5-5": "Claude Sonnet 5.5 (rapid, recomandat)",
    "claude-opus-5-5": "Claude Opus 5.5 (cel mai atent)",
    "claude-haiku-5-5": "Claude Haiku 5.5 (cel mai ieftin)",
}
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_IMAGES = 90

SYSTEM = """You are Montaj, a senior video editor for social media. You receive raw footage \
(as sampled frames with timestamps), photos, music, measured facts about each file \
(scene cuts, silences, exposure, music beats) and the user's rules. You return an edit plan \
that a renderer executes exactly with ffmpeg.

How the plan works:
- clips play in order. A video clip uses [start, end) seconds of its source; an image clip \
uses end as its on-screen duration. speed changes the on-screen length (length = (end-start)/speed).
- transition_in blends a clip with the previous one and overlaps them by transition_duration.
- overlays are timed from the start of their clip; captions are timed on the final timeline.
- color: brightness/contrast/saturation/warmth correct the shot; look adds a creative grade. \
Each file comes with a measured auto_color suggestion - start from it, then adjust for the look.
- fit: fill crops to the frame; blur_bg keeps the whole shot over a blurred copy (good when a \
horizontal shot goes into a vertical video and the subject would be cropped out).

Editing judgement:
- The user's rules come first. If they ask for something the footage can't give, do your best \
and say so in notes.
- Open with a hook: the strongest, most surprising or most beautiful moment in the first 2 seconds.
- Vary shot length; cut on action or on the beat; never keep shaky starts or dead air. \
When a clip has speech, keep whole sentences and cut out the silences listed for it.
- Use only timestamps that exist (0..duration). Choose in-points near the frames you saw.
- On-screen text is short (max ~7 words), in the user's language, and never covers faces in \
the frame you saw; prefer bottom or top accordingly.
- If there is music, set snap_to_beat true and make shots roughly a whole number of beats long.
- Say in each clip's reason what you saw in the frame that made you choose it.
- notes: concrete advice (missing shots, what to film next time, which clip is too dark).
"""


def client_for(api_key: str | None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


def _image_block(path: Path):
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def _facts(m: dict, info: dict) -> dict:
    facts = {k: m.get(k) for k in ("id", "name", "kind", "role", "duration", "width", "height",
                                   "fps", "has_audio")}
    if info.get("stats"):
        facts["exposure"] = info["stats"]
        facts["auto_color"] = info.get("auto_color")
    if info.get("scenes"):
        facts["scene_cuts"] = info["scenes"][:40]
    if info.get("silences"):
        facts["silences"] = [[s, e] for s, e in info["silences"][:40]]
    if info.get("beats") and info["beats"].get("bpm"):
        facts["bpm"] = info["beats"]["bpm"]
        facts["beats_first_32"] = info["beats"]["beats"][:32]
    if info.get("style"):
        facts["measured_style"] = info["style"]
    return facts


def media_content(media: list, analysis: dict, frames_dir: Path) -> list:
    """Facts + frames for every file. The last block carries the cache breakpoint, so a
    revision request reuses all of it from the prompt cache."""
    blocks = [{"type": "text", "text": "MEDIA FILES (facts measured with ffmpeg):\n" + json.dumps(
        [_facts(m, analysis.get(m["id"], {})) for m in media], ensure_ascii=False, indent=1)}]
    frames = [(m, f) for m in media for f in analysis.get(m["id"], {}).get("frames", [])]
    if len(frames) > MAX_IMAGES:  # thin out evenly, keeping at least one per file
        keep, per = [], {}
        for m, f in frames:
            per.setdefault(m["id"], []).append((m, f))
        budget = MAX_IMAGES
        ids = list(per)
        for idx, mid in enumerate(ids):
            share = max(1, budget // (len(ids) - idx))
            items = per[mid]
            step = max(1, len(items) / share)
            chosen = [items[int(i * step)] for i in range(min(share, len(items)))]
            keep += chosen
            budget -= len(chosen)
        frames = keep
    for m, f in frames:
        label = "EXAMPLE (style reference, do not use in the edit)" if m.get("role") == "example" else m["kind"]
        when = f" at {f['t']:.1f}s" if m["kind"] == "video" else ""
        blocks.append({"type": "text", "text": f"[{m['id']}] {m['name']} — {label}{when}"})
        path = frames_dir / f["file"]
        if path.exists():
            blocks.append(_image_block(path))
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks


def brief(settings: dict) -> str:
    style = presets.get(settings.get("preset"))
    lines = [
        f"STYLE PRESET: {style['label']} — {style['brief']}",
        f"Suggested look: {style['look']}; typical shot length: ~{style['pace']}s.",
        f"FORMAT: aspect {settings.get('aspect') or style['aspect']}, "
        f"target length about {settings.get('duration') or style['duration']} seconds.",
    ]
    if settings.get("title"):
        lines.append(f"Title / hook text: {settings['title']}")
    if settings.get("outro"):
        lines.append(f"Ending text / call to action: {settings['outro']}")
    if settings.get("captions"):
        lines.append("Add captions for anything said on camera (infer from context; keep them short).")
    lines.append("USER RULES (follow these first):\n" + (settings.get("rules") or "(none given)"))
    return "\n".join(lines)


def _call(client, model, effort, messages) -> EditPlan:
    response = client.beta.messages.parse(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        messages=messages,
        output_format=EditPlan,
        output_config={"effort": effort},
        fallbacks="default",
        betas=["server-side-fallback-2026-07-01"],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Modelul a refuzat cererea. Reformulează regulile și încearcă din nou.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Planul a fost prea lung și s-a tăiat. Cere un video mai scurt.")
    if response.parsed_output is None:
        raise RuntimeError("AI-ul nu a returnat un plan valid. Încearcă din nou.")
    return response.parsed_output


def plan_edit(media: list, analysis: dict, frames_dir: Path, settings: dict,
              api_key: str | None, model: str = DEFAULT_MODEL, effort: str = "medium") -> EditPlan:
    content = media_content(media, analysis, frames_dir)
    content.append({"type": "text", "text": brief(settings) + "\n\nMake the edit plan."})
    return _call(client_for(api_key), model, effort, [{"role": "user", "content": content}])


def revise_edit(media: list, analysis: dict, frames_dir: Path, settings: dict, plan: EditPlan,
                feedback: str, api_key: str | None, model: str = DEFAULT_MODEL,
                effort: str = "medium") -> EditPlan:
    content = media_content(media, analysis, frames_dir)
    content.append({"type": "text", "text": brief(settings) + "\n\nCURRENT PLAN:\n"
                    + plan.model_dump_json(indent=1)
                    + "\n\nThe user watched the preview and asks for these changes:\n" + feedback
                    + "\n\nReturn the complete updated plan. Keep everything they did not ask to change."})
    return _call(client_for(api_key), model, effort, [{"role": "user", "content": content}])


def describe_error(exc: Exception) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "Cheia API nu e validă. Verifică-o în Setări."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "Cheia API nu are acces la acest model."
    if isinstance(exc, anthropic.NotFoundError):
        return "Modelul ales nu e disponibil pentru contul tău."
    if isinstance(exc, anthropic.RateLimitError):
        return "Prea multe cereri (rate limit). Mai încearcă peste un minut."
    if isinstance(exc, anthropic.BadRequestError):
        return f"Cerere respinsă de API: {exc.message}"
    if isinstance(exc, anthropic.APIStatusError):
        return f"Eroare de server Anthropic ({exc.status_code}). Încearcă din nou."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Nu mă pot conecta la api.anthropic.com. Verifică internetul."
    return str(exc)
