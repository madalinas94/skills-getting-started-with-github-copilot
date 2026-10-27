"""All on-screen text as one ASS subtitle file, burned in with libass.

ASS gives us animated text (pop, slide, typewriter, zoom) and word-by-word karaoke captions
with a single ffmpeg filter, and lets libass do line wrapping and Unicode shaping.
"""

from pathlib import Path

from .plan import EditPlan, Overlay, timeline

FONT_BOLD = "Inter Display ExtraBold"
FONT_TEXT = "Inter SemiBold"
YELLOW = "&H004DE1FF"  # #FFE14D in ASS (AABBGGRR)
WHITE = "&H00FFFFFF"
BLACK = "&H00000000"
BOX = "&H70000000"


def _ts(t: float) -> str:
    cs = max(0, int(round(t * 100)))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def clean(text: str) -> str:
    """ASS reserves {, } and backslash sequences; keep user text literal."""
    return " ".join(text.replace("\\", "/").replace("{", "(").replace("}", ")").split())


def header(W: int, H: int) -> str:
    s = min(W, H)
    margin = int(W * 0.07)

    def style(name, font, size, colour, outline, shadow, border_style=1, back=BLACK, secondary=WHITE):
        return (f"Style: {name},{font},{int(s * size)},{colour},{secondary},{back if border_style == 3 else BLACK},"
                f"{back},0,0,0,0,100,100,0,0,{border_style},{outline},{shadow},2,{margin},{margin},0,1")

    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        style("title", FONT_BOLD, 0.085, WHITE, max(1, s // 360), max(1, s // 220), back="&H90000000"),
        style("caption", FONT_BOLD, 0.058, WHITE, max(2, s // 150), max(1, s // 300), back="&H80000000"),
        style("lower_third", FONT_TEXT, 0.042, WHITE, max(2, s // 90), 0, border_style=3, back=BOX),
        style("label", FONT_TEXT, 0.034, WHITE, max(2, s // 100), 0, border_style=3, back=BOX),
        style("big_word", FONT_BOLD, 0.15, YELLOW, max(3, s // 110), max(1, s // 200), back="&H90000000"),
        style("karaoke", FONT_BOLD, 0.062, WHITE, max(3, s // 130), max(1, s // 300), back="&H80000000"),
        style("bold_caption", FONT_BOLD, 0.075, WHITE, max(3, s // 110), max(1, s // 250), back="&H80000000"),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])


def anchor(style: str, position: str, W: int, H: int):
    """(alignment, x, y) for a text box."""
    vertical = H > W
    if style == "label" or position == "top":
        return (7 if style == "label" else 8), (int(W * 0.07) if style == "label" else W // 2), int(H * (0.11 if vertical else 0.08))
    if style == "lower_third" or position == "lower_third":
        return 1, int(W * 0.07), int(H * 0.82)
    if position == "center" or style in ("title", "big_word"):
        return 5, W // 2, H // 2
    # bottom: clear of the TikTok/Reels buttons on vertical video
    return 2, W // 2, int(H * (0.74 if vertical else 0.9))


def animate(kind: str, text: str, duration: float, x: int, y: int, H: int) -> str:
    ms = int(duration * 1000)
    if kind == "pop":
        return (f"{{\\pos({x},{y})\\fad(60,150)\\fscx30\\fscy30\\t(0,170,\\fscx112\\fscy112)"
                f"\\t(170,270,\\fscx100\\fscy100)}}{text}")
    if kind == "slide_up":
        return f"{{\\move({x},{y + int(H * 0.05)},{x},{y},0,280)\\fad(180,150)}}{text}"
    if kind == "zoom_out":
        return f"{{\\pos({x},{y})\\fad(0,150)\\fscx160\\fscy160\\t(0,320,0.5,\\fscx100\\fscy100)}}{text}"
    if kind == "typewriter":
        step = max(15, min(60, int(ms * 0.5 / max(1, len(text)))))
        letters = "".join(f"{{\\alpha&HFF&\\t({i * step},{i * step + 1},\\alpha&H00&)}}{c}"
                          for i, c in enumerate(text))
        return f"{{\\pos({x},{y})\\fad(0,150)}}{letters}"
    if kind == "none":
        return f"{{\\pos({x},{y})}}{text}"
    return f"{{\\pos({x},{y})\\fad(220,220)}}{text}"


def overlay_events(texts, W: int, H: int) -> list:
    """texts: [(Overlay, start, end)] on the final timeline."""
    out = []
    for o, s, e in texts:
        if e - s < 0.05:
            continue
        text = clean(o.text)
        if o.style == "big_word":
            text = text.upper()
        align, x, y = anchor(o.style, o.position, W, H)
        body = animate(getattr(o, "animation", "fade"), text, e - s, x, y, H)
        out.append(f"Dialogue: 2,{_ts(s)},{_ts(e)},{o.style},,0,0,0,,{{\\an{align}}}{body}")
    return out


def group_words(words, vertical: bool):
    """Split [[start, end, word]] into caption lines: short, and broken on pauses/punctuation."""
    max_words = 3 if vertical else 6
    lines, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w[0] - cur[-1][1] > 0.6
                    or cur[-1][2].rstrip()[-1:] in ".!?,;:"):
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def caption_events(words, style: str, W: int, H: int) -> list:
    """Word-timed captions. karaoke: active word yellow and bigger; bold: big uppercase lines
    that pop in; clean: plain lines that fade."""
    vertical = H > W
    out = []
    _, x, y = anchor("caption", "bottom", W, H)
    if style == "bold":
        y = int(H * (0.66 if vertical else 0.84))
    for line in group_words(words, vertical):
        start, end = line[0][0], max(line[-1][1], line[0][0] + 0.3)
        tokens = [clean(w[2]) for w in line]
        if style == "karaoke":
            for i, w in enumerate(line):
                s = w[0]
                e = line[i + 1][0] if i + 1 < len(line) else end
                parts = []
                for j, tok in enumerate(tokens):
                    parts.append(f"{{\\c{YELLOW}\\fscx112\\fscy112}}{tok}{{\\r}}" if j == i else tok)
                pop = "\\fscx85\\fscy85\\t(0,90,\\fscx100\\fscy100)" if i == 0 else ""
                out.append(f"Dialogue: 1,{_ts(s)},{_ts(max(e, s + 0.05))},karaoke,,0,0,0,,"
                           f"{{\\an2\\pos({x},{y}){pop}}}" + " ".join(parts))
        elif style == "bold":
            body = animate("pop", " ".join(tokens).upper(), end - start, x, y, H)
            out.append(f"Dialogue: 1,{_ts(start)},{_ts(end)},bold_caption,,0,0,0,,{{\\an2}}{body}")
        else:
            body = animate("fade", " ".join(tokens), end - start, x, y, H)
            out.append(f"Dialogue: 1,{_ts(start)},{_ts(end)},caption,,0,0,0,,{{\\an2}}{body}")
    return out


def build(plan: EditPlan, W: int, H: int, words=None) -> str | None:
    """ASS document for the whole edit, or None when there is no text at all."""
    texts = []
    for clip, start, length in timeline(plan):
        for o in clip.overlays:
            texts.append((o, start + o.start, start + min(length, o.start + o.duration)))
    for c in plan.captions:
        texts.append((Overlay(text=c.text, style="caption", position="bottom", animation="fade"), c.start, c.end))
    events = overlay_events(texts, W, H)
    if words and plan.caption_style != "none":
        events += caption_events(words, plan.caption_style, W, H)
    if not events:
        return None
    return header(W, H) + "\n" + "\n".join(events) + "\n"


def write(plan: EditPlan, W: int, H: int, dest: Path, words=None) -> bool:
    doc = build(plan, W, H, words)
    if doc is None:
        return False
    dest.write_text(doc, encoding="utf-8")
    return True
