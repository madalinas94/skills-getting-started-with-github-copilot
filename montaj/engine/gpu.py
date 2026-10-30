"""Hardware video encoding: NVIDIA (NVENC), Intel (Quick Sync), AMD (AMF), Apple (VideoToolbox).

Each encoder is tried on a tiny test clip once; the first that works is used for final renders.
"""

import subprocess

from . import ff

CANDIDATES = ["h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox"]
LABELS = {"h264_nvenc": "NVIDIA (NVENC)", "h264_qsv": "Intel (Quick Sync)", "h264_amf": "AMD (AMF)",
          "h264_videotoolbox": "Apple (VideoToolbox)", "libx264": "Procesor (x264)"}
_found = None


def detect() -> str:
    """The first hardware encoder that really works here, else libx264."""
    global _found
    if _found:
        return _found
    _found = "libx264"
    try:
        listed = subprocess.run([ff.binary("ffmpeg"), "-hide_banner", "-encoders"], capture_output=True,
                                text=True, timeout=20).stdout
    except Exception:
        return _found
    for enc in CANDIDATES:
        if enc not in listed:
            continue
        test = subprocess.run([ff.binary("ffmpeg"), "-hide_banner", "-v", "error", "-f", "lavfi", "-i",
                               "color=c=black:s=256x256:d=0.2", "-c:v", enc, "-f", "null", "-"],
                              capture_output=True, timeout=30)
        if test.returncode == 0:
            _found = enc
            break
    return _found


def args(encoder: str, preset: str, crf: int) -> list:
    """Codec arguments with roughly the quality of x264 at the given crf."""
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(crf + 1), "-b:v", "0"]
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-global_quality", str(crf + 2), "-preset", "medium"]
    if encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf + 2)]
    if encoder == "h264_videotoolbox":
        return ["-c:v", "h264_videotoolbox", "-q:v", str(max(40, 100 - crf * 2))]
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf)]
