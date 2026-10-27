"""Speech to text with word timings (faster-whisper, runs locally, free).

Optional: if faster-whisper isn't installed, everything else keeps working and captions
fall back to what the AI writes.
"""

import os
import threading

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

_models = {}
_lock = threading.Lock()


def available() -> bool:
    return WhisperModel is not None


def model_size() -> str:
    return os.environ.get("MONTAJ_WHISPER_MODEL", "small")


def _model(size: str):
    with _lock:
        if size not in _models:
            _models[size] = WhisperModel(size, device="cpu", compute_type="int8")
        return _models[size]


def transcribe(src, size: str | None = None, language: str | None = None) -> dict:
    """{"language", "text", "segments": [[s, e, text]], "words": [[s, e, word]]} in source seconds."""
    model = _model(size or model_size())
    segments, info = model.transcribe(str(src), language=language, word_timestamps=True,
                                      vad_filter=True, beam_size=5)
    segs, words = [], []
    for seg in segments:
        segs.append([round(seg.start, 2), round(seg.end, 2), seg.text.strip()])
        for w in seg.words or []:
            token = w.word.strip()
            if token:
                words.append([round(w.start, 2), round(w.end, 2), token])
    return {"language": info.language, "text": " ".join(s[2] for s in segs),
            "segments": segs, "words": words}


def words_even(text: str, start: float, duration: float):
    """Word timings spread evenly over a line (for voice-over when Whisper isn't available)."""
    tokens = text.split()
    if not tokens:
        return []
    weights = [len(t) + 2 for t in tokens]
    total = sum(weights)
    out, t = [], start
    for tok, w in zip(tokens, weights):
        d = duration * w / total
        out.append([round(t, 2), round(t + d, 2), tok])
        t += d
    return out
