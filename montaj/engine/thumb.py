"""YouTube-style thumbnails: you, cut out with a white outline, over a punchy background,
next to two or three huge words."""

import subprocess
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from . import ff

FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "InterDisplay-ExtraBold.otf"
YELLOW = (255, 225, 77)
ACCENTS = [(124, 92, 255), (255, 92, 138), (0, 170, 255), (255, 140, 0)]


def grab_frame(src: Path, t: float, kind: str) -> Image.Image:
    args = [ff.binary("ffmpeg"), "-hide_banner", "-nostdin", "-v", "error"]
    if kind == "video":
        args += ["-ss", f"{max(0, t):.3f}"]
    args += ["-i", str(src), "-frames:v", "1", "-vf", "scale='min(1920,iw)':-2", "-f", "image2pipe",
             "-vcodec", "png", "-"]
    raw = subprocess.run(args, capture_output=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(raw)).convert("RGB")


def _cutout(img: Image.Image):
    """RGBA of the person and their bounding box, or (None, None)."""
    from . import people
    if not people.available():
        return None, None
    rgb = np.asarray(img)
    if people.largest_face(rgb) is None:  # no face: the segmenter would cut out random shapes
        return None, None
    mask = people.person_mask(rgb)
    if mask.mean() < 0.02:
        return None, None
    alpha = Image.fromarray((np.clip((mask - 0.4) / 0.25, 0, 1) * 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.2))
    rgba = img.convert("RGBA")
    rgba.putalpha(alpha)
    box = alpha.point(lambda v: 255 if v > 128 else 0).getbbox()
    return rgba, box


def _background(img: Image.Image, size, accent):
    W, H = size
    bg = img.copy()
    s = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * s) + 1, int(bg.height * s) + 1))
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = bg.filter(ImageFilter.GaussianBlur(max(8, W // 70)))
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    bg = ImageEnhance.Color(bg).enhance(1.4)
    # diagonal colour wash from the accent colour into near-black
    x = np.linspace(0, 1, W)[None, :]
    y = np.linspace(0, 1, H)[:, None]
    t = np.clip(0.65 * x + 0.35 * y, 0, 1)[..., None]
    wash = (np.array(accent) * (1 - t) + np.array([12, 10, 24]) * t).astype(np.uint8)
    wash = Image.fromarray(np.broadcast_to(wash, (H, W, 3)).copy())
    return Image.blend(bg, wash, 0.45)


def _paste_person(canvas: Image.Image, rgba: Image.Image, box, target_h: int, anchor_x: float, stroke: int):
    person = rgba.crop(box)
    s = target_h / person.height
    person = person.resize((max(1, int(person.width * s)), target_h), Image.LANCZOS)
    W, H = canvas.size
    x = int(anchor_x * W - person.width / 2)
    x = max(-person.width // 4, min(W - person.width * 3 // 4, x))
    y = H - person.height + int(H * 0.02)
    alpha = person.getchannel("A")
    # drop shadow, then white outline, then the person
    shadow = alpha.filter(ImageFilter.GaussianBlur(stroke * 2))
    canvas.paste((0, 0, 0), (x + stroke * 2, y + stroke), shadow.point(lambda v: int(v * 0.6)))
    outline = alpha.filter(ImageFilter.MaxFilter(stroke * 2 + 1)).filter(ImageFilter.GaussianBlur(1))
    canvas.paste((255, 255, 255), (x, y), outline)
    canvas.paste(person, (x, y), alpha)
    return x, person.width


def _text(canvas: Image.Image, text: str, area, max_lines=3):
    """Huge uppercase words, auto-sized to the area, alternating white / yellow lines."""
    x0, y0, x1, y1 = area
    words = text.upper().split()
    if not words:
        return
    draw = ImageDraw.Draw(canvas)
    size = int((y1 - y0) / 2.2)
    while size > 24:
        font = ImageFont.truetype(str(FONT), size)
        avg = font.getlength("M") * 0.62
        lines = textwrap.wrap(" ".join(words), max(4, int((x1 - x0) / avg)), break_on_hyphens=False)
        width = max(font.getlength(line) for line in lines)
        height = len(lines) * size * 1.05
        if len(lines) <= max_lines and width <= (x1 - x0) and height <= (y1 - y0):
            break
        size -= 6
    font = ImageFont.truetype(str(FONT), size)
    stroke = max(4, size // 11)
    y = y0 + ((y1 - y0) - len(lines) * size * 1.05) / 2
    for i, line in enumerate(lines):
        draw.text((x0, y), line, font=font, fill=YELLOW if i % 2 else (255, 255, 255),
                  stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += size * 1.05


def make(img: Image.Image, text: str, dest_base: Path, accent_index: int = 0):
    """Write <dest_base>_youtube.jpg (1280x720) and <dest_base>_vertical.jpg (1080x1920)."""
    accent = ACCENTS[accent_index % len(ACCENTS)]
    rgba, box = _cutout(img)
    out = []

    yt = _background(img, (1280, 720), accent)
    if rgba is not None:
        _paste_person(yt, rgba, box, int(720 * 0.98), anchor_x=0.74, stroke=7)
        _text(yt, text, (50, 70, 700, 650))
    else:  # nobody in the frame: full picture, words over it
        yt = Image.blend(_background(img, (1280, 720), accent), img.resize((1280, 720)), 0.65)
        _text(yt, text, (60, 80, 1000, 640))
    path = Path(f"{dest_base}_youtube.jpg")
    yt.save(path, quality=92)
    out.append(path)

    vt = _background(img, (1080, 1920), accent)
    if rgba is not None:
        _paste_person(vt, rgba, box, int(1920 * 0.62), anchor_x=0.5, stroke=9)
        _text(vt, text, (70, 160, 1010, 720))
    else:
        _text(vt, text, (70, 600, 1010, 1300))
    path = Path(f"{dest_base}_vertical.jpg")
    vt.save(path, quality=92)
    out.append(path)
    return out


def best_moment(plan, media: dict, analysis: dict):
    """(media, time): the planned thumbnail, else the shot with the biggest face."""
    if plan.thumbnail and plan.thumbnail.media_id in media:
        return media[plan.thumbnail.media_id], plan.thumbnail.time
    best, best_size = None, -1.0
    for clip in plan.clips:
        m = media.get(clip.media_id)
        faces = (analysis.get(clip.media_id) or {}).get("faces") or []
        if not m:
            continue
        mid = (clip.start + clip.end) / 2 if m["kind"] == "video" else 0
        size = (analysis.get(clip.media_id) or {}).get("face_ratio") or 0
        if faces and size > best_size:
            best, best_size = (m, mid), size
    if best:
        return best
    c = plan.clips[0]
    return media[c.media_id], (c.start + c.end) / 2
