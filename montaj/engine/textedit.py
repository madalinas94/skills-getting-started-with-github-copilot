"""Edit the video by editing its transcript: delete words in the text, they leave the video."""

from .plan import EditPlan, timeline
from .tighten import _split


def transcript(plan: EditPlan, analysis: dict):
    """Words of every clip that keeps its sound: [{clip, start, words: [[s, e, w, t_timeline]]}]."""
    out = []
    for i, (clip, start, length) in enumerate(timeline(plan)):
        if not clip.keep_audio:
            continue
        words = ((analysis.get(clip.media_id) or {}).get("speech") or {}).get("words") or []
        inside = [[s, e, w, round(start + (s - clip.start) / clip.speed, 3)]
                  for s, e, w in words if clip.start - 0.05 <= s < clip.end]
        if inside:
            out.append({"clip": i, "media_id": clip.media_id, "start": start, "words": inside})
    return out


def _keep_ranges(start: float, end: float, words, cut):
    """[start, end) minus the cut words; each cut reaches halfway into the gaps around it
    so no breath or half-syllable is left behind."""
    cut_set = {(round(s, 3), round(e, 3)) for s, e in cut}
    spans = []
    for k, (s, e, _w) in enumerate(words):
        if (round(s, 3), round(e, 3)) not in cut_set:
            continue
        prev_e = words[k - 1][1] if k > 0 else start
        next_s = words[k + 1][0] if k + 1 < len(words) else end
        spans.append((max(start, (prev_e + s) / 2 if k > 0 else start),
                      min(end, (e + next_s) / 2 if k + 1 < len(words) else end)))
    spans.sort()
    keep, t = [], start
    for a, b in spans:
        if a - t > 0.25:
            keep.append((round(t, 3), round(a, 3)))
        t = max(t, b)
    if end - t > 0.25:
        keep.append((round(t, 3), round(end, 3)))
    return keep


def cut(plan: EditPlan, analysis: dict, cuts: list):
    """cuts: [{"clip": index, "s": source_start, "e": source_end}] (word timings).
    Returns (plan, words_removed)."""
    by_clip = {}
    for c in cuts:
        by_clip.setdefault(int(c["clip"]), []).append((float(c["s"]), float(c["e"])))
    out, removed = [], 0
    for i, clip in enumerate(plan.clips):
        if i not in by_clip:
            out.append(clip)
            continue
        words = [w for w in ((analysis.get(clip.media_id) or {}).get("speech") or {}).get("words") or []
                 if clip.start - 0.05 <= w[0] < clip.end]
        keep = _keep_ranges(clip.start, clip.end, words, by_clip[i])
        removed += len(by_clip[i])
        if not keep:
            continue  # every word of this clip was deleted
        pieces = _split(clip, keep, alternate=False)
        pieces[0].transition_in = clip.transition_in
        out.extend(pieces)
    if not out:
        raise ValueError("Ai șters tot textul; montajul ar rămâne gol.")
    return plan.model_copy(update={"clips": out}), removed
