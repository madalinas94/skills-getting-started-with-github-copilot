"""The edit plan: what the AI (or the automatic planner) decides, and what the renderer executes.

The same Pydantic models are the structured-output schema sent to Claude, so every field
has a description written for the model.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Aspect = Literal["9:16", "16:9", "1:1", "4:5"]
Transition = Literal["cut", "fade", "dissolve", "wipeleft", "wiperight", "slideup", "slidedown",
                     "circleopen", "zoomin", "smoothleft", "fadeblack", "fadewhite"]
Look = Literal["none", "cinematic", "warm", "cool", "vintage", "bw", "vivid", "film", "matte"]
Motion = Literal["none", "zoom_in", "zoom_out", "pan_left", "pan_right", "punch_in", "close_up"]
Fit = Literal["fill", "track", "blur_bg", "fit"]
TextStyle = Literal["title", "caption", "lower_third", "label", "big_word"]
Position = Literal["top", "center", "bottom", "lower_third"]
Animation = Literal["fade", "pop", "slide_up", "typewriter", "zoom_out", "none"]
CaptionStyle = Literal["none", "karaoke", "bold", "clean"]
BeatFx = Literal["none", "flash", "zoom", "shake", "mix"]

ASPECT_SIZE = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}


class Color(BaseModel):
    brightness: float = Field(0.0, description="-0.3..0.3, 0 = unchanged")
    contrast: float = Field(1.0, description="0.7..1.5, 1 = unchanged")
    saturation: float = Field(1.0, description="0..2, 1 = unchanged, 0 = black & white")
    warmth: float = Field(0.0, description="-1 (cooler/blue) .. 1 (warmer/orange), 0 = unchanged")
    look: Look = Field("none", description="Creative look applied on top of the correction")
    vignette: bool = Field(False, description="Darken the corners slightly")


class Overlay(BaseModel):
    text: str = Field(description="Short on-screen text (max ~7 words, no emoji)")
    start: float = Field(0.0, description="Seconds from the start of THIS clip (after speed change)")
    duration: float = Field(2.0, description="Seconds the text stays on screen")
    style: TextStyle = "caption"
    position: Position = "bottom"
    animation: Animation = Field("fade", description="How the text appears: pop and slide_up feel energetic, "
                                 "typewriter suits quotes, zoom_out suits titles")


Background = Literal["none", "portrait", "replace"]


class Broll(BaseModel):
    media_id: str = Field(description="id of a video or photo to show over the talking clip")
    at: float = Field(description="Seconds from the start of THIS clip (on screen) when the B-roll appears")
    duration: float = Field(2.0, description="1.5..4 seconds")
    source_start: float = Field(0.0, description="In-point inside the B-roll video")


class Clip(BaseModel):
    media_id: str = Field(description="id of a video or image from the media list")
    start: float = Field(0.0, description="In-point in seconds in the source (0 for images)")
    end: float = Field(description="Out-point in seconds in the source; for images the on-screen duration")
    speed: float = Field(1.0, description="0.5..2.5; >1 speeds up, <1 slow motion")
    fit: Fit = Field("fill", description="fill = crop centre, track = crop that follows the detected face "
                     "(use when a person is in a shot of another aspect), blur_bg = whole shot over a blurred copy, "
                     "fit = letterbox")
    motion: Motion = Field("none", description="Camera move; use zoom/pan (Ken Burns) on photos")
    color: Color = Field(default_factory=Color)
    transition_in: Transition = Field("cut", description="Transition from the previous clip (ignored on the first clip)")
    transition_duration: float = Field(0.4, description="0.2..1.5 seconds")
    keep_audio: bool = Field(True, description="Keep the clip's own sound (speech, ambience)")
    volume: float = Field(1.0, description="0..2 for the clip's own sound")
    overlays: List[Overlay] = Field(default_factory=list)
    broll: List[Broll] = Field(default_factory=list,
                               description="Cutaways shown full-frame while this clip's sound keeps playing; "
                               "match them to what is being said")
    background: Background = Field("none", description="portrait = blur everything behind the person, "
                                   "replace = put the person over background_media")
    background_media: Optional[str] = Field(None, description="id of a photo/video used when background=replace")
    reason: str = Field("", description="One short sentence: why this shot, here")


class Music(BaseModel):
    media_id: str = Field(description="id of an audio file from the media list")
    start: float = Field(0.0, description="Where to start inside the song, seconds")
    volume: float = Field(0.8, description="0..1.5")
    duck: bool = Field(True, description="Lower the music automatically when clips have speech")
    fade_in: float = 1.0
    fade_out: float = 2.0
    align_end: bool = Field(True, description="Start the song so that it ends exactly when the video ends")


class VoiceLine(BaseModel):
    start: float = Field(description="Seconds on the final timeline")
    text: str = Field(description="One or two spoken sentences, in the user's language")


class Caption(BaseModel):
    start: float = Field(description="Seconds on the final timeline")
    end: float
    text: str


class Thumbnail(BaseModel):
    media_id: str
    time: float = Field(0.0, description="Second in the source to grab")
    text: str = Field("", description="Short hook text for the cover, can be empty")


class EditPlan(BaseModel):
    title: str = Field(description="Working title of the edit")
    summary: str = Field(description="2-3 sentences: the story/structure of the edit")
    aspect: Aspect = "9:16"
    fps: int = Field(30, description="24, 25, 30 or 60")
    clips: List[Clip]
    music: Optional[Music] = None
    captions: List[Caption] = Field(default_factory=list,
                                    description="Extra subtitles on the final timeline. Leave empty: speech in "
                                    "clips is transcribed and captioned automatically")
    caption_style: CaptionStyle = Field("none", description="Look of the automatic word-by-word captions: "
                                        "karaoke = active word highlighted, bold = big uppercase, clean = plain")
    beat_fx: BeatFx = Field("none", description="Effect on music beats: flash, zoom pulse, shake, or mix")
    beat_fx_every: int = Field(2, description="1 = every beat, 2 = every second beat, 4 = once per bar")
    voiceover: List[VoiceLine] = Field(default_factory=list,
                                       description="Narration lines; only when the user asked for a voice-over")
    tighten: bool = Field(False, description="Cut pauses, filler sounds and repeated words out of speech (jump cuts)")
    voice_enhance: bool = Field(False, description="Studio voice: remove noise and hum, add presence and compression")
    emphasis_zoom: bool = Field(False, description="Punch in on the words the speaker stresses")
    sfx: bool = Field(False, description="Sound effects: whoosh on transitions, pop/boom when text appears")
    thumbnail: Optional[Thumbnail] = None
    snap_to_beat: bool = Field(False, description="Nudge cut points onto music beats")
    notes: List[str] = Field(default_factory=list, description="Advice for the user: what's missing, what to reshoot")


def clip_length(clip: Clip) -> float:
    """On-screen length of a clip before transitions overlap it."""
    return max(0.1, (clip.end - clip.start) / (clip.speed or 1.0))


def timeline(plan: EditPlan):
    """[(clip, timeline_start, length)] honouring transition overlaps."""
    out, t = [], 0.0
    for i, clip in enumerate(plan.clips):
        length = clip_length(clip)
        if i > 0 and clip.transition_in != "cut":
            t -= transition_len(plan.clips[i - 1], clip)
        out.append((clip, round(t, 3), round(length, 3)))
        t += length
    return out


def transition_len(prev: Clip, clip: Clip) -> float:
    if clip.transition_in == "cut":
        return 0.0
    return round(min(clip.transition_duration, clip_length(prev) / 2, clip_length(clip) / 2), 3)


def total_length(plan: EditPlan) -> float:
    tl = timeline(plan)
    return round(tl[-1][1] + tl[-1][2], 3) if tl else 0.0
