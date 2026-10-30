"""Turn an EditPlan into video files with ffmpeg.

Each clip is rendered to a normalised segment (same size, fps, pixel format, stereo 48 kHz
audio). Segments are cached by content hash, so re-rendering after a small edit only redoes
the clips that changed. A second pass joins the segments with transitions, mixes the music
(with ducking under speech), burns captions and normalises loudness for social media.
"""

import hashlib
import json
import shutil
import textwrap
from pathlib import Path

from . import ff, subs
from .tighten import VOICE_CHAIN
from .plan import ASPECT_SIZE, Clip, EditPlan, Overlay, clip_length, timeline, transition_len

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT_BOLD = "InterDisplay-ExtraBold.otf"
FONT_TEXT = "Inter-SemiBold.otf"

QUALITY = {
    # short side in px, x264 preset, crf, audio bitrate
    "preview": (480, "veryfast", 28, "128k"),
    "720p": (720, "medium", 21, "160k"),
    "1080p": (1080, "medium", 19, "192k"),
}

LOOKS = {
    "none": [],
    "cinematic": ["colorbalance=rs=-0.04:gs=0.0:bs=0.07:rh=0.07:gh=0.02:bh=-0.06",
                  "curves=preset=medium_contrast", "eq=saturation=0.92"],
    "warm": ["colorbalance=rm=0.07:gm=0.01:bm=-0.06:rh=0.04:bh=-0.03"],
    "cool": ["colorbalance=rm=-0.05:bm=0.07:bh=0.04"],
    "vintage": ["curves=preset=vintage", "eq=saturation=0.85"],
    "bw": ["hue=s=0", "curves=preset=medium_contrast"],
    "vivid": ["eq=saturation=1.3:contrast=1.06"],
    "film": ["curves=preset=increase_contrast", "eq=saturation=0.9", "noise=alls=5:allf=t"],
    "matte": ["curves=all='0/0.07 0.5/0.5 1/0.93'", "eq=saturation=0.88"],
}


# xfade's own "dissolve" is a pixel-noise effect; a soft cross-dissolve is its "fade"
XFADE = {"dissolve": "fade"}


def frame_size(aspect: str, quality: str):
    w, h = ASPECT_SIZE[aspect]
    short = QUALITY[quality][0]
    scale = short / min(w, h)

    def even8(x):
        return max(16, int(round(x * scale / 8)) * 8)

    return even8(w), even8(h)


# ----------------------------------------------------------------- per-clip filters

def track_expr(points, scale_px: str, size: int) -> str:
    """Piecewise-linear crop offset following [(t, centre 0..1)] in clip time."""
    if not points:
        return f"({scale_px}-{size})/2"
    expr = f"{points[-1][1]:.4f}"
    for (t0, v0), (t1, v1) in reversed(list(zip(points, points[1:]))):
        if t1 - t0 < 1e-3:
            continue
        expr = f"if(lt(t\\,{t1:.3f})\\,{v0:.4f}+({v1 - v0:.4f})*(t-{t0:.3f})/{t1 - t0:.3f}\\,{expr})"
    return f"clip({expr}*{scale_px}-{size}/2\\,0\\,{scale_px}-{size})"


def face_points(track, clip: Clip, L: float, axis: int, limit: int = 24):
    """Face centre keyframes in clip-output time for one axis (1 = x, 2 = y)."""
    from .vision import face_at
    if not track:
        return []
    n = max(2, min(limit, int(L / 0.5) + 1))
    pts = []
    for i in range(n):
        t = L * i / (n - 1)
        src_t = clip.start + t * clip.speed
        c = face_at(track, src_t)
        pts.append((round(t, 3), c[axis - 1]))
    return pts


def fit_filter(fit: str, W: int, H: int, src="[vin]", out="[vfit]", track=None, clip=None, L=0.0) -> str:
    if fit == "track" and track:
        xs = face_points(track, clip, L, 1)
        ys = face_points(track, clip, L, 2)
        return (f"{src}scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H}:x='{track_expr(xs, 'iw', W)}':y='{track_expr(ys, 'ih', H)}',setsar=1{out}")
    if fit == "fit":
        return (f"{src}scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1{out}")
    if fit == "blur_bg":
        bw, bh = max(16, W // 8 * 2), max(16, H // 8 * 2)  # quarter size, even
        return (f"{src}split=2[bgs][fgs];"
                f"[bgs]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
                f"boxblur=8:2,scale={W}:{H},eq=brightness=-0.07:saturation=1.1[bg];"
                f"[fgs]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1{out}")
    return (f"{src}scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1{out}")


def motion_filter(motion: str, W: int, H: int, L: float) -> list:
    """Smooth Ken Burns moves via per-frame scale + centred crop."""
    L = max(L, 0.1)
    if motion == "none":
        return []
    if motion == "close_up":  # static tighter framing, used on alternate jump cuts
        cw, ch = int(W / 1.15) // 2 * 2, int(H / 1.15) // 2 * 2
        return [f"crop={cw}:{ch}", f"scale={W}:{H}", "setsar=1"]
    if motion in ("zoom_in", "zoom_out", "punch_in"):
        if motion == "zoom_in":
            z = f"(1+0.14*t/{L:.3f})"
        elif motion == "zoom_out":
            z = f"(1.14-0.14*t/{L:.3f})"
        else:  # quick punch-in during the first 0.25 s, then hold
            z = "(1+0.1*min(t/0.25\\,1))"
        return [f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame",
                f"crop={W}:{H}:'(iw-{W})/2':'(ih-{H})/2'"]
    pw, ph = int(W * 1.16) // 2 * 2, int(H * 1.16) // 2 * 2
    x = f"(iw-{W})*t/{L:.3f}" if motion == "pan_right" else f"(iw-{W})*(1-t/{L:.3f})"
    return [f"scale={pw}:{ph}", f"crop={W}:{H}:'{x}':'(ih-{H})/2'"]


def color_filters(clip: Clip) -> list:
    c = clip.color
    out = []
    if abs(c.brightness) > 1e-3 or abs(c.contrast - 1) > 1e-3 or abs(c.saturation - 1) > 1e-3:
        out.append(f"eq=brightness={c.brightness:.3f}:contrast={c.contrast:.3f}:saturation={c.saturation:.3f}")
    if abs(c.warmth) > 1e-3:
        w = c.warmth * 0.1
        out.append(f"colorbalance=rm={w:.3f}:bm={-w:.3f}:rh={w / 2:.3f}:bh={-w / 2:.3f}")
    out += LOOKS.get(c.look, [])
    if c.vignette:
        out.append("vignette=angle=PI/5")
    return out


def _wrap(text: str, fontsize: int, W: int):
    max_chars = max(8, int(W * 0.86 / (fontsize * 0.56)))
    return textwrap.wrap(text, max_chars)[:4] or [text]


STYLE = {
    # size factor of the short side, font, colour, border, box
    "title": (0.085, FONT_BOLD, "white", 0, True),
    "caption": (0.052, FONT_BOLD, "white", 5, False),
    "lower_third": (0.042, FONT_TEXT, "white", 0, True),
    "label": (0.034, FONT_TEXT, "white", 0, True),
    "big_word": (0.15, FONT_BOLD, "0xFFE14D", 7, False),
}


def text_filters(texts, W: int, H: int, workdir: Path, prefix: str) -> list:
    """drawtext filters for [(Overlay, start, end)] with soft fade in/out.

    Text goes through textfile= so no user text ever needs filtergraph escaping.
    """
    out = []
    short = min(W, H)
    vertical = H > W
    for n, (o, s, e) in enumerate(texts):
        factor, font, colour, border, box = STYLE.get(o.style, STYLE["caption"])
        size = max(12, int(short * factor))
        lines = _wrap(o.text.upper() if o.style == "big_word" else o.text, size, W)
        line_h = int(size * 1.25)
        block = line_h * len(lines)
        if o.position == "top" or o.style == "label":
            y0 = int(H * (0.12 if vertical else 0.08))
        elif o.position == "center" or o.style in ("title", "big_word"):
            y0 = (H - block) // 2
        elif o.position == "lower_third" or o.style == "lower_third":
            y0 = int(H * 0.72)
        else:  # bottom; keep clear of the TikTok/Reels UI on vertical video
            y0 = int(H * (0.70 if vertical else 0.84)) - block // 2
        fade = min(0.25, (e - s) / 3)
        alpha = (f"if(lt(t,{s + fade:.3f}),(t-{s:.3f})/{fade:.3f},"
                 f"if(gt(t,{e - fade:.3f}),({e:.3f}-t)/{fade:.3f},1))")
        for li, line in enumerate(lines):
            fname = f"{prefix}_t{n}_{li}.txt"
            (workdir / fname).write_text(line, encoding="utf-8")
            if o.style in ("lower_third", "label"):
                x = f"{int(W * 0.06)}"
            else:
                x = "(w-text_w)/2"
            parts = [f"fontfile={font}", f"textfile={fname}", f"fontsize={size}",
                     f"fontcolor={colour}", f"x={x}", f"y={y0 + li * line_h}",
                     f"enable='between(t,{s:.3f},{e:.3f})'", f"alpha='{alpha}'"]
            if border:
                parts += [f"borderw={max(2, int(size * border / 100 * 1.6))}", "bordercolor=black@0.85"]
            if box:
                parts += ["box=1", "boxcolor=black@0.5", f"boxborderw={int(size * 0.35)}"]
            else:
                parts += ["shadowcolor=black@0.5", f"shadowx={max(1, size // 25)}", f"shadowy={max(1, size // 25)}"]
            out.append("drawtext=" + ":".join(parts))
    return out


def atempo_chain(speed: float) -> list:
    chain, s = [], speed
    while s > 2.0:
        chain.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        chain.append("atempo=0.5")
        s /= 0.5
    chain.append(f"atempo={s:.4f}")
    return chain


def _copy_fonts(workdir: Path):
    for f in (FONT_BOLD, FONT_TEXT):
        if not (workdir / f).exists():
            shutil.copy(FONT_DIR / f, workdir / f)


def segment_key(clip: Clip, m: dict, W: int, H: int, fps: int, quality: str, track=None, opts=None) -> str:
    # text is burned on the whole timeline, so editing it never re-renders segments
    blob = json.dumps({"clip": clip.model_dump(exclude={"reason", "overlays"}), "src": m["file"],
                       "size": [W, H], "fps": fps, "q": quality, "track": track if clip.fit == "track" else None,
                       "opts": opts or {}, "v": 6}, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def _source_size(m: dict, cap: int = 1920):
    """Even working size for compositing at (at most) source resolution."""
    w, h = m.get("width") or 1920, m.get("height") or 1080
    s = min(1.0, cap / max(w, h))
    return max(16, int(w * s) // 2 * 2), max(16, int(h * s) // 2 * 2)


def render_segment(clip: Clip, m: dict, src: Path, dest: Path, W: int, H: int, fps: int,
                   quality: str, workdir: Path, track=None, opts=None):
    """One clip → normalised segment. opts: enhance (studio voice), mask (person mask video),
    bg (background media path + kind), broll ([(Broll, path, media)]), audio (replacement audio
    file for this source, e.g. the music-only stem when dubbing)."""
    opts = opts or {}
    L = clip_length(clip)
    _, preset, crf, abr = QUALITY[quality]
    args, n_in = [], 0

    def add_input(*a):
        nonlocal n_in
        args.extend(a)
        n_in += 1
        return n_in - 1

    if m["kind"] == "image":
        main = add_input("-loop", "1", "-framerate", str(fps), "-t", f"{L + 0.5:.3f}", "-i", src)
    else:
        main = add_input("-ss", f"{clip.start:.3f}", "-t", f"{clip.end - clip.start:.3f}", "-i", src)
    silence = add_input("-f", "lavfi", "-t", f"{L + 0.5:.3f}", "-i", "anullsrc=r=48000:cl=stereo")

    retime = f"setpts=(PTS-STARTPTS)/{clip.speed:.4f},fps={fps}"
    pre = []
    if "denoise" in clip.enhance:
        pre.append("hqdn3d=3:2.5:6:5")
    if "stabilize" in clip.enhance and m["kind"] == "video":
        pre += stabilize_filters(src, clip, workdir, dest.stem)
    vf = [f"[{main}:v]{retime},format=yuv420p{',' + ','.join(pre) if pre else ''}[raw]"]
    base = "[raw]"

    # Beauty: smooth and lift only facial skin (mask from face detection × skin colour)
    if clip.beauty > 0.01 and opts.get("skin"):
        SW, SH = _source_size(m)
        sk = add_input(*(["-stream_loop", "-1", "-t", f"{L + 0.5:.3f}"] if m["kind"] == "image" else []),
                       "-i", opts["skin"])
        amount = min(1.0, clip.beauty)
        vf.append(f"[{sk}:v]{retime},scale={SW}:{SH},format=gray,lutyuv=y=val*{amount:.2f}[skin]")
        vf.append(f"{base}scale={SW}:{SH},setsar=1,split=2[bo][bs]")
        vf.append(f"[bs]gblur=sigma={2 + 4 * amount:.1f},eq=brightness={0.035 * amount:.3f}:saturation=0.97,"
                  f"format=yuva420p[bsm];[bsm][skin]alphamerge[bsa];[bo][bsa]overlay=0:0,format=yuv420p[beauty]")
        base = "[beauty]"

    # Person cut-out: composite at source size, before framing, so every later step
    # (crop, face tracking, Ken Burns, grade) treats person + background as one picture.
    if clip.background != "none" and opts.get("mask"):
        SW, SH = _source_size(m)
        mk = add_input(*(["-stream_loop", "-1", "-t", f"{L + 0.5:.3f}"] if m["kind"] == "image" else []),
                       "-i", opts["mask"])
        vf.append(f"[{mk}:v]{retime},scale={SW}:{SH},format=gray[mask]")
        vf.append(f"{base}scale={SW}:{SH},setsar=1,split=2[fgsrc][bgsrc]")
        if clip.background == "replace" and opts.get("bg"):
            bg_path, bg_kind = opts["bg"]
            bi = add_input(*(["-loop", "1", "-framerate", str(fps)] if bg_kind == "image" else ["-stream_loop", "-1"]),
                           "-t", f"{L + 0.5:.3f}", "-i", bg_path)
            vf.append(f"[{bi}:v]setpts=PTS-STARTPTS,fps={fps},scale={SW}:{SH}:force_original_aspect_ratio=increase,"
                      f"crop={SW}:{SH},setsar=1[bgv];[bgsrc]nullsink")
        else:  # portrait mode: strong blur behind the person
            vf.append(f"[bgsrc]scale={SW // 4 // 2 * 2}:{SH // 4 // 2 * 2},boxblur=10:3,scale={SW}:{SH},"
                      f"eq=brightness=-0.03,setsar=1[bgv]")
        vf.append("[fgsrc]format=yuva420p[fga];[fga][mask]alphamerge[fg]")
        vf.append("[bgv][fg]overlay=0:0:shortest=0,format=yuv420p[comp]")
        base = "[comp]"

    if clip.split_with and opts.get("split"):
        # two cameras stacked: this one on top, the other below, each framed on its face
        s_path, s_media, s_track = opts["split"]
        si = add_input("-ss", f"{max(0, clip.start + clip.split_offset):.3f}", "-t", f"{clip.end - clip.start:.3f}",
                       "-i", s_path)
        half = H // 2 // 2 * 2
        vf.append(f"[{si}:v]{retime},format=yuv420p[sraw]")
        vf.append(fit_filter("track" if track else "fill", W, half, src=base, out="[top]", track=track, clip=clip, L=L))
        vf.append(fit_filter("track" if s_track else "fill", W, H - half, src="[sraw]", out="[bot]",
                             track=s_track, clip=clip.model_copy(update={"start": clip.start + clip.split_offset}), L=L))
        vf.append(f"[top][bot]vstack=inputs=2,setsar=1[vfit]")
    else:
        vf.append(fit_filter(clip.fit if clip.fit != "track" or track else "fill", W, H, src=base,
                             track=track, clip=clip, L=L))
    chain = motion_filter(clip.motion, W, H, L) + color_filters(clip)
    if "sharpen" in clip.enhance:
        chain.append("unsharp=5:5:0.9:3:3:0.3")
    chain += ["tpad=stop_mode=clone:stop_duration=1", "setsar=1", "format=yuv420p"]
    vf.append("[vfit]" + ",".join(chain) + "[v0]")

    # B-roll cut-aways over the clip; its sound keeps playing underneath
    cur = "[v0]"
    for k, (b, bpath, bm) in enumerate(opts.get("broll") or []):
        dur = max(0.3, min(b.duration, L - b.at))
        if dur <= 0.3 or b.at >= L:
            continue
        if bm["kind"] == "image":
            bi = add_input("-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", bpath)
        else:
            bi = add_input("-ss", f"{min(b.source_start, max(0, bm['duration'] - dur)):.3f}",
                           "-t", f"{dur:.3f}", "-i", bpath)
        grade = ",".join(color_filters(clip)) or "null"
        vf.append(f"[{bi}:v]setpts=PTS-STARTPTS+{b.at:.3f}/TB,fps={fps},"
                  f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,{grade},"
                  f"format=yuv420p[br{k}]")
        vf.append(f"{cur}[br{k}]overlay=0:0:eof_action=pass:enable='between(t,{b.at:.3f},{b.at + dur:.3f})'[vb{k}]")
        cur = f"[vb{k}]"
    if clip.pip and opts.get("pip"):
        cur = _pip(vf, add_input, clip, opts["pip"], cur, W, H, L, fps, retime, workdir)
    vf.append(f"{cur}null[v]")

    if clip.keep_audio and m.get("has_audio") and m["kind"] == "video":
        a_src = f"[{main}:a]"
        if opts.get("audio"):
            ai = add_input("-ss", f"{clip.start:.3f}", "-t", f"{clip.end - clip.start:.3f}", "-i", opts["audio"])
            a_src = f"[{ai}:a]"
        af = ([f"{a_src}asetpts=PTS-STARTPTS"] + atempo_chain(clip.speed) +
              (VOICE_CHAIN if opts.get("enhance") else []) +
              [f"volume={clip.volume:.3f}", "aresample=48000",
               "aformat=sample_fmts=fltp:channel_layouts=stereo",
               "afade=t=in:d=0.03", "apad"])
        vf.append(",".join(af) + "[a]")
    else:
        vf.append(f"[{silence}:a]anull[a]")

    args += ["-filter_complex", ";".join(vf), "-map", "[v]", "-map", "[a]",
             "-t", f"{L:.3f}", "-r", str(fps),
             "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", abr, "-ar", "48000", "-ac", "2", dest.name]
    ff.run(args, cwd=workdir)


# ----------------------------------------------------------------- whole edit

def _has_filter(name: str) -> bool:
    if not hasattr(_has_filter, "names"):
        import subprocess
        out = subprocess.run([ff.binary("ffmpeg"), "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        _has_filter.names = {line.split()[1] for line in out.splitlines() if len(line.split()) > 2}
    return name in _has_filter.names


def stabilize_filters(src, clip: Clip, workdir: Path, stem: str) -> list:
    """vid.stab two-pass when ffmpeg has it (smooth, like a gimbal), deshake otherwise."""
    if _has_filter("vidstabdetect"):
        trf = f"{stem}.trf"
        ff.run(["-ss", f"{clip.start:.3f}", "-t", f"{clip.end - clip.start:.3f}", "-i", src,
                "-vf", f"vidstabdetect=shakiness=6:accuracy=12:result={trf}", "-f", "null", "-"], cwd=workdir)
        return [f"vidstabtransform=input={trf}:smoothing=18:zoom=4:optzoom=0", "unsharp=5:5:0.6:3:3:0.3"]
    return ["deshake=rx=24:ry=24:edge=mirror", "scale=iw*1.05:ih*1.05", "crop=iw/1.05:ih/1.05"]


def _bubble_masks(size: int, shape: str, workdir: Path):
    """Alpha mask and white ring PNGs for the facecam bubble."""
    from PIL import Image, ImageDraw
    mask_p, ring_p = workdir / f"pip_{shape}_{size}_m.png", workdir / f"pip_{shape}_{size}_r.png"
    if not mask_p.exists():
        big = size * 4
        m = Image.new("L", (big, big), 0)
        r = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        dm, dr = ImageDraw.Draw(m), ImageDraw.Draw(r)
        ring = max(8, big // 40)
        if shape == "circle":
            dm.ellipse((ring, ring, big - ring, big - ring), fill=255)
            dr.ellipse((ring // 2, ring // 2, big - ring // 2, big - ring // 2), outline=(255, 255, 255, 255), width=ring)
        else:
            rad = big // 6
            dm.rounded_rectangle((ring, ring, big - ring, big - ring), rad, fill=255)
            dr.rounded_rectangle((ring // 2, ring // 2, big - ring // 2, big - ring // 2), rad,
                                 outline=(255, 255, 255, 255), width=ring)
        m.resize((size, size), Image.LANCZOS).save(mask_p)
        r.resize((size, size), Image.LANCZOS).save(ring_p)
    return mask_p.name, ring_p.name


def _pip(vf, add_input, clip: Clip, pip_opts, cur: str, W: int, H: int, L: float, fps: int, retime: str,
         workdir: Path) -> str:
    path, face = pip_opts
    p = clip.pip
    size = int(min(W, H) * max(0.15, min(0.5, p.size))) // 2 * 2
    margin = int(min(W, H) * 0.04)
    x = margin if "left" in p.position else W - size - margin
    y = margin if "top" in p.position else H - size - int(H * (0.2 if H > W else 0.05)) - margin
    mask, ring = _bubble_masks(size, p.shape, workdir)
    ci = add_input("-ss", f"{max(0, clip.start + p.offset):.3f}", "-t", f"{clip.end - clip.start:.3f}", "-i", path)
    mi = add_input("-loop", "1", "-t", f"{L + 0.5:.3f}", "-i", mask)
    ri = add_input("-loop", "1", "-t", f"{L + 0.5:.3f}", "-i", ring)
    cx, cy = face or (0.5, 0.4)
    # square crop centred on the face, a little headroom above it
    crop = (f"crop='min(iw,ih)*0.8':'min(iw,ih)*0.8':"
            f"'clip({cx:.3f}*iw-min(iw,ih)*0.4,0,iw-min(iw,ih)*0.8)':'clip({cy:.3f}*ih-min(iw,ih)*0.35,0,ih-min(iw,ih)*0.8)'")
    vf.append(f"[{ci}:v]{retime},{crop},scale={size}:{size},setsar=1,format=yuva420p[cam]")
    vf.append(f"[{mi}:v]format=gray,setsar=1[cmask];[cam][cmask]alphamerge[camc]")
    vf.append(f"{cur}[camc]overlay={x}:{y}:eof_action=pass[pv1]")
    vf.append(f"[{ri}:v]format=rgba[ring];[pv1][ring]overlay={x}:{y}:shortest=0[pv2]")
    return "[pv2]"


def mask_key(clip: Clip) -> str:
    return f"{clip.media_id}:{clip.start:.3f}:{clip.end:.3f}"


def _segment_opts(clip: Clip, plan: EditPlan, media: dict, media_dir: Path, extras: dict) -> dict:
    opts = {}
    if plan.voice_enhance and clip.keep_audio:
        opts["enhance"] = True
    mask = (extras.get("masks") or {}).get(mask_key(clip))
    if clip.background != "none" and mask:
        opts["mask"] = str(mask)
        bm = media.get(clip.background_media or "")
        if clip.background == "replace" and bm and bm["kind"] in ("image", "video"):
            opts["bg"] = (str(media_dir / bm["file"]), bm["kind"])
    brolls = []
    for b in clip.broll:
        bm = media.get(b.media_id)
        if bm and bm["kind"] in ("image", "video") and b.media_id != clip.media_id:
            brolls.append((b, str(media_dir / bm["file"]), bm))
    if brolls:
        opts["broll"] = brolls
    skin = (extras.get("skins") or {}).get(mask_key(clip))
    if clip.beauty > 0.01 and skin:
        opts["skin"] = str(skin)
    if clip.pip:
        pm = media.get(clip.pip.media_id)
        if pm and pm["kind"] == "video":
            track = (extras.get("faces_all") or {}).get(clip.pip.media_id) or []
            face = None
            if track:
                face = (sum(t[1] for t in track) / len(track), sum(t[2] for t in track) / len(track))
            opts["pip"] = (str(media_dir / pm["file"]), face)
    if clip.split_with:
        sm = media.get(clip.split_with)
        if sm and sm["kind"] == "video":
            opts["split"] = (str(media_dir / sm["file"]), sm, (extras.get("faces_all") or {}).get(clip.split_with))
    audio = (extras.get("bg_audio") or {}).get(clip.media_id)
    if audio:
        opts["audio"] = str(audio)
    return opts


def render(plan: EditPlan, media: dict, media_dir: Path, workdir: Path, out_path: Path,
           quality: str = "preview", on_progress=None, extras: dict | None = None) -> dict:
    """Render the plan to out_path. Returns {"duration", "width", "height"}.

    extras (see timing.prepare): words for captions, beat grid, voice-over tracks, face tracks,
    person masks, emphasis moments, sound effects, dubbing stems and mute ranges.
    """
    extras = extras or {}
    workdir.mkdir(parents=True, exist_ok=True)
    cache = workdir / "segments"
    cache.mkdir(exist_ok=True)
    _copy_fonts(cache)
    _copy_fonts(workdir)
    W, H = frame_size(plan.aspect, quality)
    fps = plan.fps
    progress = on_progress or (lambda p, msg="": None)

    segs = []
    n = len(plan.clips)
    for i, clip in enumerate(plan.clips):
        m = media[clip.media_id]
        track = ((extras.get("faces") or {}).get(clip.media_id) or (extras.get("faces_all") or {}).get(clip.media_id)
                 if clip.fit == "track" or clip.split_with else None)
        opts = _segment_opts(clip, plan, media, media_dir, extras)
        key_opts = {k: (v if k not in ("broll", "split") else
                        ([(b.model_dump(), p) for b, p, _m in v] if k == "broll" else [v[0], v[2]]))
                    for k, v in opts.items()}
        key = segment_key(clip, m, W, H, fps, quality, track, key_opts)
        seg = cache / f"seg_{key}.mp4"
        if not seg.exists():
            progress(0.65 * i / n, f"Randez clipul {i + 1}/{n}")
            tmp = cache / f"tmp_{key}.mp4"
            render_segment(clip, m, media_dir / m["file"], tmp, W, H, fps, quality, cache, track, opts)
            tmp.replace(seg)
        segs.append(seg)
    progress(0.65, "Lipesc clipurile, tranziții și muzică")

    total = _join(plan, media, media_dir, segs, workdir, out_path, W, H, fps, quality, extras,
                  lambda p: progress(0.65 + 0.35 * p, "Lipesc clipurile, tranziții și muzică"))
    progress(1.0, "Gata")
    return {"duration": total, "width": W, "height": H}


def beat_filters(kind: str, grid: dict, every: int, W: int, H: int, total: float) -> list:
    """Per-frame effects that hit on the music's beats."""
    if kind == "none" or not grid:
        return []
    per = grid["period"] * max(1, every)
    ph = grid["phase"]
    # P: 1 on the beat, decaying to 0 over 0.15 s
    p = f"(gte(t\\,{ph:.4f})*max(0\\,1-mod(t-{ph:.4f}\\,{per:.4f})/0.15))"
    out = []
    if kind in ("zoom", "mix"):
        z = f"(1+0.07*{p})"
        out += [f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame",
                f"crop={W}:{H}:'(iw-{W})/2':'(ih-{H})/2'"]
    if kind == "shake":
        pw, ph2 = int(W * 1.08) // 2 * 2, int(H * 1.08) // 2 * 2
        out += [f"scale={pw}:{ph2}",
                f"crop={W}:{H}:'(iw-{W})/2+{0.03 * W:.1f}*{p}*sin(t*83)':'(ih-{H})/2+{0.025 * H:.1f}*{p}*cos(t*71)'"]
    if kind in ("flash", "mix"):
        amount = 0.25 if kind == "flash" else 0.12
        out.append(f"eq=brightness='{amount}*{p}':eval=frame")
    return out + ["setsar=1"]


def emphasis_filters(moments, W: int, H: int) -> list:
    """Punch-in on stressed words: ease to 1.12x, hold, ease back."""
    if not moments:
        return []
    terms = []
    for a, b in moments[:40]:
        terms.append(f"min(max((t-{a:.3f})/0.12\\,0)\\,1)*min(max(({b:.3f}-t)/0.18\\,0)\\,1)")
    z = f"(1+0.12*min(1\\,{'+'.join(terms)}))"
    return [f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame",
            f"crop={W}:{H}:'(iw-{W})/2':'(ih-{H})/2'", "setsar=1"]


def _mute_expr(ranges) -> str:
    """volume expression: original speech down to 6% inside the dubbed ranges."""
    inside = "+".join(f"between(t\\,{a:.3f}\\,{b:.3f})" for a, b in ranges[:120])
    return f"volume='if({inside}\\,0.06\\,1)':eval=frame"


def _join(plan, media, media_dir, segs, workdir, out_path, W, H, fps, quality, extras, on_progress):
    _, preset, crf, abr = QUALITY[quality]
    args, fc = [], []
    for seg in segs:
        args += ["-i", seg]
    for i in range(len(segs)):
        fc.append(f"[{i}:v]settb=AVTB,setsar=1,setpts=PTS-STARTPTS[v{i}]")
        fc.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")
    n_in = len(segs)

    tl = timeline(plan)
    cur_v, cur_a, cur_len = "[v0]", "[a0]", tl[0][2]
    for i in range(1, len(segs)):
        clip, prev = plan.clips[i], plan.clips[i - 1]
        L = tl[i][2]
        d = transition_len(prev, clip)
        ov, oa = f"[jv{i}]", f"[ja{i}]"
        if d <= 0:
            fc.append(f"{cur_v}{cur_a}[v{i}][a{i}]concat=n=2:v=1:a=1[cv{i}][ca{i}]")
            fc.append(f"[cv{i}]settb=AVTB{ov}")
            fc.append(f"[ca{i}]anull{oa}")
            cur_len += L
        else:
            off = max(0.0, cur_len - d)
            kind = XFADE.get(clip.transition_in, clip.transition_in)
            fc.append(f"{cur_v}[v{i}]xfade=transition={kind}:duration={d:.3f}:offset={off:.3f}{ov}")
            fc.append(f"{cur_a}[a{i}]acrossfade=d={d:.3f}:c1=tri:c2=tri{oa}")
            cur_len += L - d
        cur_v, cur_a = ov, oa
    total = round(cur_len, 3)

    # Look (LUT), emphasis punch-ins, beat effects, then all text in one ASS pass
    vf = []
    if extras.get("lut") and Path(extras["lut"]).exists():
        lut_name = f"look_{Path(extras['lut']).stem}.cube"
        shutil.copy(extras["lut"], workdir / lut_name)
        vf.append(f"lut3d=file={lut_name}:interp=tetrahedral")
    vf += emphasis_filters(extras.get("emphasis"), W, H)
    vf += beat_filters(plan.beat_fx, extras.get("beat"), plan.beat_fx_every, W, H, total)
    ass_name = f"{out_path.stem}.ass"
    if subs.write(plan, W, H, workdir / ass_name, extras.get("words"), extras.get("key_words") or ()):
        vf.append(f"ass={ass_name}:fontsdir=.")
    final_v = "[vout]"
    cues = subs.emoji_cues(extras.get("words") or [], plan.caption_style, W, H) if plan.emoji else []
    fc.append(f"{cur_v}" + ",".join(vf + ["format=yuv420p"]) + ("[vtxt]" if cues else final_v))
    if cues:  # emoji pop in above the captions
        prev = "[vtxt]"
        for k, c in enumerate(cues[:30]):
            d = c["end"] - c["start"]
            args += ["-loop", "1", "-t", f"{d:.3f}", "-i", c["file"]]
            sz = c["size"]
            fc.append(f"[{n_in}:v]format=rgba,scale=w='trunc({sz}*(0.5+0.5*min(1\\,t/0.14))/2)*2':h=-2:eval=frame,"
                      f"fade=t=in:st=0:d=0.1:alpha=1,fade=t=out:st={max(0, d - 0.15):.3f}:d=0.15:alpha=1,"
                      f"setpts=PTS-STARTPTS+{c['start']:.3f}/TB[em{k}]")
            out_l = final_v if k == min(len(cues), 30) - 1 else f"[ve{k}]"
            fc.append(f"{prev}[em{k}]overlay=x='{W // 2}-w/2':y='{c['y'] + sz}-h':eof_action=pass:"
                      f"enable='between(t,{c['start']:.3f},{c['end']:.3f})'{out_l}")
            prev = out_l
            n_in += 1

    voice = cur_a
    if extras.get("mute"):  # dubbing without separated stems: duck the original speech
        fc.append(f"{voice}{_mute_expr(extras['mute'])}[muted]")
        voice = "[muted]"
    any_voice = any(c.keep_audio and media[c.media_id].get("has_audio") for c in plan.clips)
    tracks = extras.get("voice") or []
    if tracks:
        labels = [voice]
        for k, tr in enumerate(tracks):
            args += ["-i", tr["file"]]
            ms = int(tr["start"] * 1000)
            tempo = tr.get("tempo") or 1.0
            stretch = "," + ",".join(atempo_chain(tempo)) if abs(tempo - 1) > 0.01 else ""
            fc.append(f"[{n_in}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo{stretch},"
                      f"adelay={ms}|{ms},volume=1.6[vo{k}]")
            n_in += 1
            labels.append(f"[vo{k}]")
        fc.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0[voices]")
        voice, any_voice = "[voices]", True
    if plan.music:
        mu = plan.music
        m = media[mu.media_id]
        args += ["-stream_loop", "-1", "-ss", f"{mu.start:.3f}", "-i", media_dir / m["file"]]
        mi = n_in
        n_in += 1
        fo = min(mu.fade_out, total / 3)
        fc.append(f"[{mi}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                  f"aformat=sample_fmts=fltp:channel_layouts=stereo,volume={mu.volume:.3f},"
                  f"afade=t=in:d={min(mu.fade_in, total / 3):.3f},"
                  f"afade=t=out:st={max(0, total - fo):.3f}:d={fo:.3f}[mus]")
        if mu.duck and any_voice:
            fc.append(f"{voice}asplit=2[vo1][vo2]")
            fc.append("[mus][vo1]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=350[duck]")
            fc.append("[vo2][duck]amix=inputs=2:duration=first:normalize=0[mix]")
        else:
            fc.append(f"{voice}[mus]amix=inputs=2:duration=first:normalize=0[mix]")
        voice = "[mix]"
    sfx = [s for s in (extras.get("sfx") or []) if s["start"] < total - 0.1]
    if sfx:  # after ducking, so effects never push the music down
        labels = [voice]
        for k, s in enumerate(sfx[:60]):
            args += ["-i", s["file"]]
            ms = max(0, int(s["start"] * 1000))
            fc.append(f"[{n_in}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                      f"volume={s.get('volume', 0.5):.2f},adelay={ms}|{ms}[sx{k}]")
            n_in += 1
            labels.append(f"[sx{k}]")
        fc.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0[withsfx]")
        voice = "[withsfx]"
    # loudnorm turns pure digital silence into NaNs the encoder rejects, so only normalise real sound
    audible = any_voice or plan.music or sfx
    fc.append(f"{voice}{'loudnorm=I=-14:TP=-1.5:LRA=11,' if audible else ''}aresample=48000[aout]")

    tmp = out_path.with_suffix(".part.mp4")
    args += ["-filter_complex", ";".join(fc), "-map", final_v, "-map", "[aout]",
             "-t", f"{total:.3f}", "-r", str(fps),
             "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", abr, "-ar", "48000", "-movflags", "+faststart",
             str(tmp.resolve())]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # cwd=workdir: fonts and caption text files are referenced by bare name
    ff.run_progress(args, total, on_progress, cwd=workdir)
    tmp.replace(out_path)
    return total


# ----------------------------------------------------------------- extra outputs

def export_mp3(video: Path, dest: Path):
    ff.run(["-i", video, "-vn", "-c:a", "libmp3lame", "-q:a", "2", dest])


def export_cover(plan: EditPlan, media: dict, media_dir: Path, workdir: Path, dest_base: Path,
                 quality: str = "1080p"):
    """Cover image (JPG + PNG) for the post: chosen frame, same grade, hook text."""
    th = plan.thumbnail
    clip = None
    if th:
        clip = next((c for c in plan.clips if c.media_id == th.media_id), None)
    if not th or clip is None:
        clip = plan.clips[0]
        th_media, th_time, th_text = clip.media_id, clip.start, plan.title
    else:
        th_media, th_time, th_text = th.media_id, th.time, th.text or plan.title
    m = media[th_media]
    W, H = frame_size(plan.aspect, quality)
    _copy_fonts(workdir)
    args = []
    if m["kind"] == "video":
        args += ["-ss", f"{min(th_time, max(0, m['duration'] - 0.1)):.3f}"]
    args += ["-i", media_dir / m["file"]]
    chain = color_filters(clip)
    if th_text:
        chain += text_filters([(Overlay(text=th_text, style="title", position="center"), 0, 9999)],
                              W, H, workdir, "cover")
    fc = fit_filter(clip.fit, W, H, "[0:v]", "[f]") + ";[f]" + ",".join(chain or ["null"]) + "[o]"
    jpg, png = dest_base.with_suffix(".jpg"), dest_base.with_suffix(".png")
    for target in (jpg, png):
        ff.run([*args, "-filter_complex", fc, "-map", "[o]", "-frames:v", "1",
                *(["-q:v", "2"] if target.suffix == ".jpg" else []), str(target.resolve())],
               cwd=workdir)
    return jpg, png
