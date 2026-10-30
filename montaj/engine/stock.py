"""Free stock B-roll from Pexels or Pixabay (both need a free API key), with credits kept."""

import hashlib
import re
from pathlib import Path

import httpx2

STOP = {"care", "este", "sunt", "pentru", "acest", "aceasta", "despre", "foarte", "toate", "acum", "atunci",
        "unde", "cand", "când", "pentru", "dintre", "asupra", "fiindcă", "pentru", "nostru", "noastră", "voastră",
        "about", "there", "their", "which", "would", "could", "should", "these", "those", "really", "because"}


class StockError(RuntimeError):
    pass


def _orientation(aspect: str) -> str:
    return {"9:16": "portrait", "4:5": "portrait", "1:1": "square"}.get(aspect, "landscape")


def _pick(files, short_side=1080):
    """The mp4 rendition closest to the output size without going under 720p if possible."""
    files = [f for f in files if f.get("link") and f.get("width") and f.get("height")]
    if not files:
        return None
    return min(files, key=lambda f: abs(min(f["width"], f["height"]) - short_side) + (5000 if min(f["width"], f["height"]) < 640 else 0))


def search_pexels(query: str, aspect: str, key: str):
    r = httpx2.get("https://api.pexels.com/videos/search", headers={"Authorization": key}, timeout=30,
                   params={"query": query, "orientation": _orientation(aspect), "per_page": 8, "size": "medium"})
    if r.status_code in (401, 403):
        raise StockError("Cheia Pexels nu e validă (Setări).")
    r.raise_for_status()
    out = []
    for v in r.json().get("videos", []):
        f = _pick(v.get("video_files", []))
        if f and 2 <= (v.get("duration") or 0) <= 60:
            out.append({"url": f["link"], "duration": v["duration"], "source": "Pexels",
                        "credit": f"{(v.get('user') or {}).get('name', 'Pexels')} / Pexels — {v.get('url', '')}"})
    return out


def search_pixabay(query: str, aspect: str, key: str):
    r = httpx2.get("https://pixabay.com/api/videos/", timeout=30,
                   params={"key": key, "q": query, "per_page": 8, "safesearch": "true"})
    if r.status_code in (400, 401, 403):
        raise StockError("Cheia Pixabay nu e validă (Setări).")
    r.raise_for_status()
    out = []
    for v in r.json().get("hits", []):
        sizes = [dict(link=s.get("url"), width=s.get("width"), height=s.get("height"))
                 for s in (v.get("videos") or {}).values()]
        f = _pick(sizes)
        if f:
            out.append({"url": f["link"], "duration": v.get("duration"), "source": "Pixabay",
                        "credit": f"{v.get('user', 'Pixabay')} / Pixabay — {v.get('pageURL', '')}"})
    return out


def fetch(query: str, aspect: str, dest_dir: Path, pexels_key=None, pixabay_key=None):
    """Download the best match for the query. Returns {path, credit, query} or None."""
    if not (pexels_key or pixabay_key):
        raise StockError("Pentru B-roll de pe internet pune o cheie gratuită Pexels sau Pixabay în Setări.")
    found = []
    if pexels_key:
        found = search_pexels(query, aspect, pexels_key)
    if not found and pixabay_key:
        found = search_pixabay(query, aspect, pixabay_key)
    if not found:
        return None
    best = found[0]
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:30] or "stock"
    dest = dest_dir / f"stock_{name}_{hashlib.sha1(best['url'].encode()).hexdigest()[:8]}.mp4"
    if not dest.exists():
        with httpx2.stream("GET", best["url"], timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_bytes(1 << 16):
                    f.write(chunk)
    return {"path": dest, "credit": best["credit"], "query": query}


def queries_from_words(words, count: int):
    """No AI: the most specific words said, as search terms (longest, not stop words)."""
    seen, out = set(), []
    cands = sorted({re.sub(r"[^\w]", "", w[2].lower()) for w in words}, key=len, reverse=True)
    for w in cands:
        if len(w) >= 5 and w not in STOP and w not in seen:
            seen.add(w)
            out.append(w)
        if len(out) >= count:
            break
    return out
