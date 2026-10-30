"""The AI editor: Claude looks at the frames, reads the rules and returns an EditPlan.

Also: reviews its own rendered preview, and writes the social-media copy for the post.
"""

import base64
import json
from pathlib import Path
from typing import List

import anthropic
from pydantic import BaseModel, Field

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
(scene cuts, silences, exposure, shaky/blurry/dark ranges, face positions, speech transcripts \
with timestamps, music tempo and mood) and the user's rules. You return an edit plan that a \
renderer executes exactly with ffmpeg.

How the plan works:
- clips play in order. A video clip uses [start, end) seconds of its source; an image clip \
uses end as its on-screen duration. speed changes the on-screen length (length = (end-start)/speed).
- transition_in blends a clip with the previous one and overlaps them by transition_duration.
- overlays are timed from the start of their clip; captions and voiceover on the final timeline.
- color: brightness/contrast/saturation/warmth correct the shot; look adds a creative grade. \
Each file comes with a measured auto_color suggestion - start from it, then adjust for the look.
- fit: fill crops the centre; track crops around the detected face and follows it (use it when \
a file has faces and its orientation differs from the output); blur_bg keeps the whole shot over \
a blurred copy.
- Speech in clips with keep_audio is transcribed and captioned word by word automatically in \
caption_style; do not copy the transcript into captions.
- beat_fx adds flashes / zoom pulses / shake on the music's beats.
- music.align_end makes the song end together with the video.
- broll: while someone talks, cut away to another file that shows what they are talking about \
(use the transcript to time it); the talking clip's sound keeps playing.
- background: portrait blurs what is behind the person; replace puts them over another file.
- When the user allows stock footage and nothing in the media list shows what is being said, a \
B-roll may use media_id "stock:<short English search query>" (e.g. "stock:city night traffic"); \
the app downloads a free clip from Pexels/Pixabay.
- tighten removes pauses and "ăăă" from speech; voice_enhance cleans the voice; emphasis_zoom \
punches in on stressed words; sfx adds whooshes and pops. Turn them on when the brief asks or \
when talking-head footage would clearly benefit.

Editing judgement:
- The user's rules come first. If they ask for something the footage can't give, do your best \
and say so in notes.
- Open with a hook: the strongest, most surprising or most beautiful moment in the first 2 \
seconds. With speech, the hook can be the most striking sentence from the transcript.
- Vary shot length; cut on action or on the beat. Never use the shaky, blurry or dark ranges \
listed for a file unless nothing else exists.
- When a clip has speech, cut on sentence boundaries from the transcript and drop the silences.
- Use only timestamps that exist (0..duration). Choose in-points near the frames you saw.
- On-screen text is short (max ~7 words), in the user's language, and never covers faces; use \
the face positions (cx, cy are 0..1 of the frame) to choose top or bottom.
- If there is music, set snap_to_beat true and make shots roughly a whole number of beats long. \
If several songs are available pick the one whose mood and tempo fit the brief.
- Say in each clip's reason what you saw in the frame that made you choose it.
- notes: concrete advice (missing shots, what to film next time, which clip is too dark).
"""


class Review(BaseModel):
    score: int = Field(description="1-10: how well the preview meets the user's rules and works as a social video")
    verdict: str = Field(description="One sentence, in Romanian, for the user")
    problems: List[str] = Field(default_factory=list, description="Concrete problems you see, in Romanian")
    fixes: str = Field("", description="Instructions for the next revision, addressed to the editor (English)")


class PostCopy(BaseModel):
    platform: str
    caption: str = Field(description="Ready-to-paste post text in the user's language")
    hashtags: List[str]


class SocialCopy(BaseModel):
    hooks: List[str] = Field(description="3 alternative opening hook lines")
    posts: List[PostCopy] = Field(description="TikTok, Instagram Reels, YouTube Shorts")
    youtube_title: str
    best_time: str = Field(description="Short advice on when to post, in Romanian")


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
    if info.get("quality"):
        facts["quality_score"] = info["quality"].get("score")
        facts["bad_ranges"] = info["quality"].get("issues", [])[:20]
    if info.get("faces"):
        step = max(1, len(info["faces"]) // 12)
        facts["face_positions"] = info["faces"][::step]
        facts["face_ratio"] = info.get("face_ratio")
    if info.get("speech"):
        facts["transcript"] = info["speech"]["segments"][:80]
        facts["language"] = info["speech"].get("language")
    if info.get("beats") and info["beats"].get("bpm"):
        facts["bpm"] = info["beats"]["bpm"]
        facts["beats_first_32"] = info["beats"]["beats"][:32]
    if info.get("mood"):
        facts["mood"] = info["mood"]
    if info.get("style"):
        facts["measured_style"] = info["style"]
    return facts


def media_content(media: list, analysis: dict, frames_dir: Path) -> list:
    """Facts + frames for every file. The last block carries the cache breakpoint, so
    revisions, variants and reviews reuse all of it from the prompt cache."""
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


def brief(settings: dict, style: dict | None = None) -> str:
    style = style or presets.get(settings.get("preset"))
    lines = [
        f"STYLE: {style['label']} — {style['brief']}",
        f"Suggested look: {style['look']}; typical shot length: ~{style['pace']}s; "
        f"transitions: {', '.join(style['transitions'][:6])}; text animations: {', '.join(style.get('animations', ['fade']))}.",
        f"FORMAT: aspect {settings.get('aspect') or style['aspect']}, "
        f"target length about {settings.get('duration') or style['duration']} seconds.",
        f"Caption style for speech: {settings.get('caption_style') or style.get('captions', 'none')}. "
        f"Beat effects: {settings.get('beat_fx') or style.get('beat_fx', 'none')} "
        f"(every {style.get('beat_every', 2)} beats).",
        f"Music should {'end together with the video' if settings.get('music_align', True) else 'just fade out at the end'}.",
    ]
    if style.get("color"):
        lines.append(f"Saved grade to reuse: {json.dumps(style['color'])}.")
    if settings.get("title"):
        lines.append(f"Title / hook text: {settings['title']}")
    if settings.get("outro"):
        lines.append(f"Ending text / call to action: {settings['outro']}")
    if settings.get("voiceover"):
        idea = settings.get("voiceover_text") or "(write it yourself from what you see)"
        lines.append("VOICE-OVER: write narration lines in the user's language (about 2.5 words per second "
                     f"of screen time, leave room between lines). Script or idea from the user: {idea}")
    extras = [name for key, name in (("tighten", "tighten=true (cut pauses and fillers)"),
                                     ("voice_enhance", "voice_enhance=true"),
                                     ("emphasis_zoom", "emphasis_zoom=true"), ("sfx", "sfx=true"),
                                     ("auto_broll", "add B-roll over talking clips where it fits"),
                                     ("stock_broll", "stock footage allowed for B-roll (stock:<query>)"),
                                     ("emoji", "emoji=true"))
              if settings.get(key)]
    if extras:
        lines.append("The user switched on: " + "; ".join(extras) + ".")
    ins = settings.get("insights")
    if ins:
        lines.append("WHAT WORKS WITH THIS CREATOR'S AUDIENCE (from their analytics): " + json.dumps(
            {k: ins.get(k) for k in ("summary", "do", "dont", "best_length", "hook_tips") if ins.get(k)},
            ensure_ascii=False))
    if settings.get("variant"):
        lines.append(f"VARIANT: {settings['variant']}")
    lines.append("USER RULES (follow these first):\n" + (settings.get("rules") or "(none given)"))
    return "\n".join(lines)


def _parse(client, model, effort, messages, schema, system=SYSTEM, max_tokens=16000):
    response = client.beta.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        output_format=schema,
        output_config={"effort": effort},
        fallbacks="default",
        betas=["server-side-fallback-2026-07-01"],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Modelul a refuzat cererea. Reformulează regulile și încearcă din nou.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Răspunsul AI a fost prea lung și s-a tăiat. Cere un video mai scurt.")
    if response.parsed_output is None:
        raise RuntimeError("AI-ul nu a returnat un răspuns valid. Încearcă din nou.")
    return response.parsed_output


def plan_edit(media: list, analysis: dict, frames_dir: Path, settings: dict,
              api_key: str | None, model: str = DEFAULT_MODEL, effort: str = "medium",
              style: dict | None = None) -> EditPlan:
    content = media_content(media, analysis, frames_dir)
    content.append({"type": "text", "text": brief(settings, style) + "\n\nMake the edit plan."})
    return _parse(client_for(api_key), model, effort, [{"role": "user", "content": content}], EditPlan)


def revise_edit(media: list, analysis: dict, frames_dir: Path, settings: dict, plan: EditPlan,
                feedback: str, api_key: str | None, model: str = DEFAULT_MODEL,
                effort: str = "medium", style: dict | None = None) -> EditPlan:
    content = media_content(media, analysis, frames_dir)
    content.append({"type": "text", "text": brief(settings, style) + "\n\nCURRENT PLAN:\n"
                    + plan.model_dump_json(indent=1)
                    + "\n\nChanges requested:\n" + feedback
                    + "\n\nReturn the complete updated plan. Keep everything not asked to change."})
    return _parse(client_for(api_key), model, effort, [{"role": "user", "content": content}], EditPlan)


REVIEW_SYSTEM = """You are a demanding social-media video producer reviewing an editor's draft. \
You see frames sampled from the rendered preview (with their time on the timeline), the edit \
plan and the user's brief. Judge it as the target audience would: is the hook strong in the \
first 2 seconds, is the pacing right, is anything dark, shaky, repetitive or badly framed, is \
the text readable and not covering faces, does it follow every user rule. Score honestly; 8+ \
means ready to post."""


def review_preview(frames: list, plan: EditPlan, settings: dict, api_key: str | None,
                   model: str = DEFAULT_MODEL, effort: str = "medium", style: dict | None = None) -> Review:
    """frames: [(timeline_seconds, jpg_path)] from the rendered preview."""
    content = []
    for t, path in frames:
        content.append({"type": "text", "text": f"Preview at {t:.1f}s"})
        content.append(_image_block(Path(path)))
    content.append({"type": "text", "text": "BRIEF:\n" + brief(settings, style) + "\n\nPLAN:\n"
                    + plan.model_dump_json(indent=1) + "\n\nReview this draft."})
    return _parse(client_for(api_key), model, effort, [{"role": "user", "content": content}], Review,
                  system=REVIEW_SYSTEM, max_tokens=8000)


COPY_SYSTEM = """You write social-media copy for short videos. Natural, specific to what is \
in the video, in the user's language (Romanian unless the brief says otherwise), no clichés, \
no fake claims. Hashtags: 5-10, mixing broad and niche, without the # sign."""


def social_copy(frames: list, plan: EditPlan, settings: dict, api_key: str | None,
                model: str = DEFAULT_MODEL) -> SocialCopy:
    content = []
    for t, path in frames[:6]:
        content.append(_image_block(Path(path)))
    content.append({"type": "text", "text": f"Video: {plan.title}\n{plan.summary}\n\nUser rules: "
                    + (settings.get("rules") or "-") + "\n\nWrite the post copy."})
    return _parse(client_for(api_key), model, "low", [{"role": "user", "content": content}], SocialCopy,
                  system=COPY_SYSTEM, max_tokens=4000)


def template_copy(plan: EditPlan) -> SocialCopy:
    """No-AI fallback so the export always has a starting point."""
    tags = ["video", "reels", "tiktok", "romania", "vlog"]
    return SocialCopy(
        hooks=[plan.title, f"Stai până la final: {plan.title.lower()}", "Nu mă așteptam la asta…"],
        posts=[PostCopy(platform=p, caption=f"{plan.title} ✨", hashtags=tags)
               for p in ("TikTok", "Instagram Reels", "YouTube Shorts")],
        youtube_title=plan.title, best_time="Seara, între 19:00 și 21:00, când lumea e pe telefon.")


SHORTS_SYSTEM = """You are a short-form video producer who turns long videos (podcasts, vlogs, \
talks) into Shorts / Reels / TikToks. From the timestamped transcript and a few frames, pick the \
moments that work on their own: a strong first sentence, one clear idea, an emotional or \
surprising payoff. Each moment starts and ends on sentence boundaries. Score honestly."""


def find_moments(transcript: list, frames: list, duration: float, count: int, settings: dict,
                 api_key: str | None, model: str = DEFAULT_MODEL, effort: str = "medium"):
    """transcript: [[start, end, text]]; frames: [(t, path)]. Returns shorts.Moments."""
    from .shorts import Moments
    content = []
    for t, path in frames[:16]:
        content.append({"type": "text", "text": f"Frame at {t:.0f}s"})
        content.append(_image_block(Path(path)))
    lines = "\n".join(f"[{s:.1f}-{e:.1f}] {text}" for s, e, text in transcript)
    content.append({"type": "text", "text": f"VIDEO LENGTH: {duration:.0f}s\nTRANSCRIPT:\n{lines}\n\n"
                    f"USER RULES: {settings.get('rules') or '-'}\n\nFind the {count} best moments, "
                    "each 20-60 seconds, not overlapping, best first."})
    return _parse(client_for(api_key), model, effort, [{"role": "user", "content": content}], Moments,
                  system=SHORTS_SYSTEM)


TRANSLATE_SYSTEM = """You translate the speech of a social video for dubbing. Translate meaning \
and tone, not word by word; keep the speaker's personality, slang level and humour. Each line \
will be spoken in the original line's time slot, so keep it about as long to say as the \
original (shorter is better than longer). Translate on-screen texts too, keeping them short."""


def translate(units: list, overlays: list, title: str, language: str, api_key: str | None,
              model: str = DEFAULT_MODEL):
    """Returns dub.Translation for one target language."""
    from .dub import Translation
    payload = {"target_language": language, "title": title,
               "lines": [{"id": u["id"], "seconds": round(u["end"] - u["start"], 1), "text": u["text"]} for u in units],
               "overlays": overlays}
    content = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=1)}]
    return _parse(client_for(api_key), model, "low", [{"role": "user", "content": content}], Translation,
                  system=TRANSLATE_SYSTEM)


class Insights(BaseModel):
    summary: str = Field(description="2-3 sentences in Romanian: what this audience rewards")
    do: List[str] = Field(description="Concrete things to keep doing (Romanian)")
    dont: List[str] = Field(description="Concrete things to stop doing (Romanian)")
    best_length: str = Field(description="Ideal video length for this channel, e.g. '35-45 s'")
    hook_tips: List[str] = Field(description="Hook patterns that worked, with examples from the titles")


INSIGHTS_SYSTEM = """You are a YouTube / short-form growth analyst. From a creator's own video \
statistics (views, average view duration and percentage, retention curves where available) \
find what their audience rewards: topics, title/hook patterns, length, pacing. Be specific to \
this data; no generic advice."""


def channel_insights(videos: list, api_key: str | None, model: str = DEFAULT_MODEL) -> Insights:
    content = [{"type": "text", "text": json.dumps(videos[:40], ensure_ascii=False, indent=1)}]
    return _parse(client_for(api_key), model, "medium", [{"role": "user", "content": content}], Insights,
                  system=INSIGHTS_SYSTEM, max_tokens=6000)


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
