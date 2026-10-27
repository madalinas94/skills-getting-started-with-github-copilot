"""Shot quality (dark / blurry / shaky) and face tracking from low-resolution grey frames.

numpy is required; OpenCV is optional and only used for face detection. Without it the
quality checks still run and face tracking is simply reported as unavailable.
"""

import subprocess

import numpy as np

from . import ff

try:
    import cv2
    _CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
except Exception:  # OpenCV missing or broken install
    cv2 = None
    _CASCADE = None

SCAN_FPS = 4
SCAN_W = 480
MAX_SECONDS = 180


def faces_available() -> bool:
    return _CASCADE is not None and not _CASCADE.empty()


def _frames(src, media: dict):
    """Yield (t, grey uint8 array HxW) at SCAN_FPS."""
    mw, mh = media.get("width") or 16, media.get("height") or 9
    h = max(2, int(round(SCAN_W * mh / mw / 2)) * 2)
    vf = f"fps={SCAN_FPS},scale={SCAN_W}:{h},format=gray"
    args = [ff.binary("ffmpeg"), "-hide_banner", "-nostdin", "-v", "error"]
    if media["kind"] == "image":
        args += ["-i", str(src), "-frames:v", "1", "-vf", f"scale={SCAN_W}:{h},format=gray"]
    else:
        args += ["-t", str(MAX_SECONDS), "-i", str(src), "-an", "-vf", vf]
    args += ["-f", "rawvideo", "-"]
    raw = subprocess.run(args, capture_output=True).stdout
    size = SCAN_W * h
    for i in range(len(raw) // size):
        frame = np.frombuffer(raw, np.uint8, size, i * size).reshape(h, SCAN_W)
        yield i / SCAN_FPS, frame


def _sharpness(g: np.ndarray) -> float:
    g = g.astype(np.float32)
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    return float(lap.var())


def _shift(a: np.ndarray, b: np.ndarray):
    """Global translation between two frames (phase correlation), in pixels."""
    a = a[::2, ::2].astype(np.float32)
    b = b[::2, ::2].astype(np.float32)
    win = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    fa, fb = np.fft.fft2((a - a.mean()) * win), np.fft.fft2((b - b.mean()) * win)
    r = fa * np.conj(fb)
    r /= np.abs(r) + 1e-6
    corr = np.abs(np.fft.ifft2(r))
    y, x = np.unravel_index(np.argmax(corr), corr.shape)
    if y > a.shape[0] // 2:
        y -= a.shape[0]
    if x > a.shape[1] // 2:
        x -= a.shape[1]
    if x == 0 and y == 0:
        return 0.0, 0.0
    # Only camera movement shifts the whole frame: aligning must cut the difference clearly,
    # otherwise the peak came from something moving inside the shot.
    m = max(abs(int(x)), abs(int(y))) + 1
    if 4 * m >= min(a.shape):  # a jump this big is a cut or a whip-pan, not shake
        return 0.0, 0.0
    inner = (slice(m, -m), slice(m, -m))
    before = np.abs(b - a)[inner].mean()
    after = np.abs(np.roll(b, (int(y), int(x)), axis=(0, 1)) - a)[inner].mean()
    if after > 0.6 * before:
        return 0.0, 0.0
    return 2.0 * x, 2.0 * y


def _face(g: np.ndarray):
    """Largest face as (cx, cy, size), normalised to the frame, or None."""
    found = _CASCADE.detectMultiScale(g, scaleFactor=1.08, minNeighbors=4, minSize=(24, 24))
    if len(found) == 0:
        return None
    x, y, w, h = max(found, key=lambda f: f[2] * f[3])
    H, W = g.shape
    return ((x + w / 2) / W, (y + h / 2) / H, w / W)


def _smooth_track(samples, duration):
    """Fill gaps (hold / interpolate) and smooth the face centre so the crop glides."""
    if not samples:
        return []
    ts = np.array([s[0] for s in samples])
    xs = np.array([s[1] for s in samples])
    ys = np.array([s[2] for s in samples])
    grid = np.arange(0, max(duration, ts[-1]) + 1e-6, 0.5)
    gx = np.interp(grid, ts, xs)
    gy = np.interp(grid, ts, ys)
    k = np.ones(3) / 3
    if len(grid) >= 3:
        gx = np.convolve(np.pad(gx, 1, mode="edge"), k, mode="valid")
        gy = np.convolve(np.pad(gy, 1, mode="edge"), k, mode="valid")
    return [[round(float(t), 2), round(float(x), 3), round(float(y), 3)] for t, x, y in zip(grid, gx, gy)]


def scan(src, media: dict) -> dict:
    """Per-second quality flags, merged problem ranges, a 0-100 score and a face track."""
    times, lum, sharp, shifts, face_samples = [], [], [], [], []
    prev = None
    for t, g in _frames(src, media):
        times.append(t)
        lum.append(float(g.mean()))
        sharp.append(_sharpness(g))
        shifts.append(_shift(prev, g) if prev is not None else (0.0, 0.0))
        prev = g
        if faces_available():
            f = _face(g)
            if f:
                face_samples.append((t, *f))
    if not times:
        return {"issues": [], "score": None, "faces": [], "face_ratio": 0.0}

    lum, sharp = np.array(lum), np.array(sharp)
    sh = np.array(shifts)
    # shake = what's left after removing the smooth (intentional) camera motion
    if len(sh) >= 5:
        k = np.ones(5) / 5
        smooth = np.stack([np.convolve(np.pad(sh[:, i], 2, mode="edge"), k, mode="valid") for i in (0, 1)], 1)
        jitter = np.linalg.norm(sh - smooth, axis=1)
    else:
        jitter = np.zeros(len(sh))
    ref = np.percentile(sharp, 90) if len(sharp) > 3 else sharp.max()

    flags = []
    seconds = int(np.ceil(times[-1] + 1e-6)) or 1
    for s in range(seconds):
        idx = [i for i, t in enumerate(times) if s <= t < s + 1] or [min(len(times) - 1, s * SCAN_FPS)]
        f = []
        if lum[idx].mean() < 42:
            f.append("dark")
        if lum[idx].mean() > 235:
            f.append("bright")
        if sharp[idx].mean() < max(12.0, 0.25 * ref):
            f.append("blurry")
        if jitter[idx].mean() > 6.0:
            f.append("shaky")
        flags.append(f)

    issues = []
    for kind in ("shaky", "blurry", "dark", "bright"):
        start = None
        for s, f in enumerate(flags + [[]]):
            if kind in f and start is None:
                start = s
            elif kind not in f and start is not None:
                issues.append({"kind": kind, "start": float(start),
                               "end": float(min(s, media.get("duration") or s))})
                start = None
    bad = sum(1 for f in flags if f) / len(flags)
    duration = media.get("duration") or (times[-1] + 1 / SCAN_FPS)
    return {
        "issues": issues,
        "score": int(round(100 * (1 - bad))),
        "faces": _smooth_track(face_samples, duration) if face_samples else [],
        "face_ratio": round(len(face_samples) / len(times), 2) if faces_available() else None,
    }


def face_at(track, t: float):
    """Interpolated (cx, cy) of the face track at source time t."""
    if not track:
        return None
    ts = [p[0] for p in track]
    return (float(np.interp(t, ts, [p[1] for p in track])), float(np.interp(t, ts, [p[2] for p in track])))
