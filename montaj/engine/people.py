"""People in the picture: face detection and person cutout masks (MediaPipe, runs locally).

Both models ship in assets/models (Apache 2.0). If MediaPipe isn't installed the app falls
back to OpenCV face detection and the background features are reported as unavailable.
"""

import subprocess
import threading
from pathlib import Path

import numpy as np

from . import ff

MODELS = Path(__file__).resolve().parent.parent / "assets" / "models"
MASK_W = 480
MASK_FPS = 15

try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision as mpv
except Exception:  # not installed, or missing system libraries
    mp = None

_local = threading.local()


def _segmenter():
    if not hasattr(_local, "seg"):
        opts = mpv.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=str(MODELS / "selfie_segmenter.tflite")),
            output_confidence_masks=True)
        _local.seg = mpv.ImageSegmenter.create_from_options(opts)
    return _local.seg


def _detector():
    if not hasattr(_local, "faces"):
        opts = mpv.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=str(MODELS / "blaze_face_short_range.tflite")),
            min_detection_confidence=0.55)
        _local.faces = mpv.FaceDetector.create_from_options(opts)
    return _local.faces


def available() -> bool:
    if mp is None:
        return False
    try:
        _segmenter()
        return True
    except Exception:
        return False


def person_mask(rgb: np.ndarray) -> np.ndarray:
    """Float mask 0..1 (H, W) of the person(s) in an RGB uint8 image."""
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    result = _segmenter().segment(image)
    return result.confidence_masks[0].numpy_view()[..., 0].copy()


def largest_face(rgb: np.ndarray):
    """(cx, cy, size) normalised to the image, or None."""
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    found = _detector().detect(image).detections
    if not found:
        return None
    h, w = rgb.shape[:2]
    b = max(found, key=lambda d: d.bounding_box.width * d.bounding_box.height).bounding_box
    return ((b.origin_x + b.width / 2) / w, (b.origin_y + b.height / 2) / h, b.width / w)


def _size(media: dict, width: int):
    mw, mh = media.get("width") or 16, media.get("height") or 9
    return width, max(2, int(round(width * mh / mw / 2)) * 2)


def mask_video(src: Path, media: dict, start: float, duration: float, dest: Path) -> Path:
    """Grey mask video of the person for [start, start+duration) of the source, cached.

    Low resolution and 15 fps on purpose: the renderer scales and retimes it together with
    the picture, and a temporal blend keeps the edge from flickering.
    """
    if dest.exists():
        return dest
    w, h = _size(media, MASK_W)
    read = [ff.binary("ffmpeg"), "-hide_banner", "-nostdin", "-v", "error"]
    if media["kind"] == "image":
        read += ["-i", str(src), "-frames:v", "1"]
    else:
        read += ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(src), "-r", str(MASK_FPS)]
    read += ["-an", "-vf", f"scale={w}:{h},format=rgb24", "-f", "rawvideo", "-"]
    tmp = dest.with_suffix(".tmp.mkv")
    write = subprocess.Popen([ff.binary("ffmpeg"), "-hide_banner", "-nostdin", "-v", "error", "-y",
                              "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", str(MASK_FPS),
                              "-i", "-", "-c:v", "ffv1", str(tmp)], stdin=subprocess.PIPE)
    reader = subprocess.Popen(read, stdout=subprocess.PIPE)
    size = w * h * 3
    prev = None
    try:
        while True:
            raw = reader.stdout.read(size)
            if len(raw) < size:
                break
            m = person_mask(np.frombuffer(raw, np.uint8).reshape(h, w, 3))
            m = m if prev is None else 0.55 * m + 0.45 * prev  # temporal smoothing
            prev = m
            # soft but decisive edge
            out = np.clip((m - 0.35) / 0.3, 0, 1)
            write.stdin.write((out * 255).astype(np.uint8).tobytes())
    finally:
        reader.stdout.close()
        reader.wait()
        write.stdin.close()
        write.wait()
    if write.returncode != 0 or not tmp.exists():
        raise ff.FFmpegError("Nu am putut crea masca pentru decuparea persoanei.")
    tmp.replace(dest)
    return dest


def skin_mask_video(src: Path, media: dict, start: float, duration: float, dest: Path) -> Path:
    """Grey mask of facial skin (face area × skin colour), for the beauty filter, cached."""
    import cv2
    if dest.exists():
        return dest
    w, h = _size(media, MASK_W)
    read = [ff.binary("ffmpeg"), "-hide_banner", "-nostdin", "-v", "error"]
    if media["kind"] == "image":
        read += ["-i", str(src), "-frames:v", "1"]
    else:
        read += ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(src), "-r", str(MASK_FPS)]
    read += ["-an", "-vf", f"scale={w}:{h},format=rgb24", "-f", "rawvideo", "-"]
    tmp = dest.with_suffix(".tmp.mkv")
    write = subprocess.Popen([ff.binary("ffmpeg"), "-hide_banner", "-nostdin", "-v", "error", "-y",
                              "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", str(MASK_FPS),
                              "-i", "-", "-c:v", "ffv1", str(tmp)], stdin=subprocess.PIPE)
    reader = subprocess.Popen(read, stdout=subprocess.PIPE)
    size = w * h * 3
    prev, face = None, None
    try:
        while True:
            raw = reader.stdout.read(size)
            if len(raw) < size:
                break
            rgb = np.frombuffer(raw, np.uint8).reshape(h, w, 3)
            found = largest_face(rgb)
            face = found or face  # hold the last face through a missed detection
            m = np.zeros((h, w), np.float32)
            if face:
                cx, cy, fw = face
                ellipse = np.zeros((h, w), np.uint8)
                cv2.ellipse(ellipse, (int(cx * w), int(cy * h)), (int(fw * w * 0.62), int(fw * w * 0.85)),
                            0, 0, 360, 255, -1)
                ycc = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
                skin = cv2.inRange(ycc, (40, 133, 77), (255, 178, 133))
                m = cv2.GaussianBlur((ellipse & skin).astype(np.float32) / 255, (0, 0), 3)
            m = m if prev is None else 0.6 * m + 0.4 * prev
            prev = m
            write.stdin.write((np.clip(m, 0, 1) * 255).astype(np.uint8).tobytes())
    finally:
        reader.stdout.close()
        reader.wait()
        write.stdin.close()
        write.wait()
    if write.returncode != 0 or not tmp.exists():
        raise ff.FFmpegError("Nu am putut crea masca pentru filtrul beauty.")
    tmp.replace(dest)
    return dest
