"""YouTube: upload (with scheduled publishing) and channel analytics; plus a YouTube Studio
CSV import for people who don't want to connect their account.

Uses the user's own Google Cloud OAuth client (type "Desktop app"), so tokens never leave
their computer.
"""

import csv
import io
import json
import time
import urllib.parse
from pathlib import Path

import httpx2

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]


class PublishError(RuntimeError):
    pass


def auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    q = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
         "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent", "state": state}
    return f"{AUTH}?{urllib.parse.urlencode(q)}"


def exchange_code(client_id: str, secret: str, code: str, redirect_uri: str) -> dict:
    r = httpx2.post(TOKEN, data={"code": code, "client_id": client_id, "client_secret": secret,
                                 "redirect_uri": redirect_uri, "grant_type": "authorization_code"}, timeout=30)
    if r.status_code >= 400:
        raise PublishError(f"Google a refuzat conectarea: {r.text[:200]}")
    return r.json()


def access_token(client_id: str, secret: str, refresh_token: str) -> str:
    r = httpx2.post(TOKEN, data={"client_id": client_id, "client_secret": secret,
                                 "refresh_token": refresh_token, "grant_type": "refresh_token"}, timeout=30)
    if r.status_code >= 400:
        raise PublishError("Conexiunea YouTube a expirat. Conectează din nou contul (Setări).")
    return r.json()["access_token"]


def upload(token: str, video: Path, title: str, description: str, tags: list, publish_at: str | None = None,
           privacy: str = "private", thumbnail: Path | None = None, on_progress=None) -> str:
    """Resumable upload. publish_at (ISO 8601, UTC) schedules it; the video stays private until then."""
    status = {"privacyStatus": "private" if publish_at else privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        status["publishAt"] = publish_at
    meta = {"snippet": {"title": title[:100], "description": description[:4900], "tags": tags[:30],
                        "categoryId": "22"}, "status": status}
    size = video.stat().st_size
    r = httpx2.post("https://www.googleapis.com/upload/youtube/v3/videos",
                    params={"uploadType": "resumable", "part": "snippet,status"},
                    headers={"Authorization": f"Bearer {token}", "X-Upload-Content-Type": "video/mp4",
                             "X-Upload-Content-Length": str(size)}, json=meta, timeout=60)
    if r.status_code >= 400:
        raise PublishError(f"YouTube a refuzat încărcarea: {r.text[:300]}")
    location = r.headers["Location"]
    chunk = 8 * 1024 * 1024
    sent = 0
    with video.open("rb") as f:
        while sent < size:
            data = f.read(chunk)
            end = sent + len(data) - 1
            r = httpx2.put(location, content=data, timeout=300,
                           headers={"Authorization": f"Bearer {token}", "Content-Length": str(len(data)),
                                    "Content-Range": f"bytes {sent}-{end}/{size}"})
            sent = end + 1
            if on_progress:
                on_progress(sent / size)
            if r.status_code in (200, 201):
                break
            if r.status_code != 308:
                raise PublishError(f"Încărcarea s-a oprit ({r.status_code}): {r.text[:200]}")
    video_id = r.json()["id"]
    if thumbnail and thumbnail.exists():
        httpx2.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set", params={"videoId": video_id},
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
                    content=thumbnail.read_bytes(), timeout=60)  # needs a verified channel; ignored otherwise
    return video_id


def channel_stats(token: str, days: int = 90, limit: int = 15) -> list:
    """Top videos of the last N days with retention metrics and titles."""
    end = time.strftime("%Y-%m-%d")
    start = time.strftime("%Y-%m-%d", time.localtime(time.time() - days * 86400))
    h = {"Authorization": f"Bearer {token}"}
    r = httpx2.get("https://youtubeanalytics.googleapis.com/v2/reports", headers=h, timeout=60, params={
        "ids": "channel==MINE", "startDate": start, "endDate": end, "dimensions": "video",
        "metrics": "views,averageViewDuration,averageViewPercentage,likes,subscribersGained",
        "sort": "-views", "maxResults": limit})
    if r.status_code >= 400:
        raise PublishError(f"YouTube Analytics: {r.text[:200]}")
    rows = r.json().get("rows") or []
    ids = [row[0] for row in rows]
    titles, durations = {}, {}
    if ids:
        v = httpx2.get("https://www.googleapis.com/youtube/v3/videos", headers=h, timeout=60,
                       params={"part": "snippet,contentDetails", "id": ",".join(ids)}).json()
        for it in v.get("items", []):
            titles[it["id"]] = it["snippet"]["title"]
            durations[it["id"]] = it["contentDetails"]["duration"]
    out = []
    for vid, views, avd, avp, likes, subs in rows:
        item = {"title": titles.get(vid, vid), "views": views, "avg_view_seconds": avd, "avg_percent": avp,
                "likes": likes, "subs": subs, "length": durations.get(vid, "")}
        rr = httpx2.get("https://youtubeanalytics.googleapis.com/v2/reports", headers=h, timeout=60, params={
            "ids": "channel==MINE", "startDate": start, "endDate": end, "dimensions": "elapsedVideoTimeRatio",
            "metrics": "audienceWatchRatio", "filters": f"video=={vid}"})
        if rr.status_code < 400:
            curve = rr.json().get("rows") or []
            item["retention"] = [[round(a, 2), round(b, 3)] for a, b in curve[::10]]
        out.append(item)
    return out


def _num(v: str) -> float:
    v = (v or "").replace(",", "").replace("%", "").strip()
    if ":" in v:  # 0:01:23 / 1:23
        parts = [float(p) for p in v.split(":")]
        sec = 0.0
        for p in parts:
            sec = sec * 60 + p
        return sec
    try:
        return float(v)
    except ValueError:
        return 0.0


def parse_studio_csv(data: bytes) -> list:
    """YouTube Studio → Analytics → Advanced mode → Export → 'Table data.csv'. Column names
    differ by language, so match them loosely."""
    text = data.decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return []

    def col(*names):
        for k in rows[0].keys():
            low = k.lower()
            if any(n in low for n in names):
                return k
        return None
    c_title = col("title", "titlu")
    c_views = col("views", "vizionări", "vizualiz")
    c_avd = col("average view duration", "durata medie")
    c_avp = col("average percentage", "procentaj", "procent")
    c_len = col("duration", "durată")
    out = []
    for r in rows:
        title = (r.get(c_title) or "").strip() if c_title else ""
        if not title or title.lower() in ("total", "totaluri"):
            continue
        out.append({"title": title, "views": _num(r.get(c_views, "")) if c_views else 0,
                    "avg_view_seconds": _num(r.get(c_avd, "")) if c_avd else 0,
                    "avg_percent": _num(r.get(c_avp, "")) if c_avp else 0,
                    "length": r.get(c_len, "") if c_len and c_len != c_avd else ""})
    return sorted(out, key=lambda x: -x["views"])


def basic_insights(videos: list) -> dict:
    """No-AI summary: what the best videos have in common."""
    if not videos:
        return {}
    top = videos[: max(1, len(videos) // 3)]
    rest = videos[len(top):] or top
    avg = lambda xs, k: sum(x[k] for x in xs) / max(1, len(xs))  # noqa: E731
    return {
        "summary": f"Cele mai bune {len(top)} video-uri au în medie {avg(top, 'avg_percent'):.0f}% vizionat "
                   f"și {avg(top, 'avg_view_seconds'):.0f}s pe vizualizare, față de {avg(rest, 'avg_percent'):.0f}% la restul.",
        "do": [f"Repetă formatul: „{v['title']}”" for v in top[:3]],
        "dont": [f"Evită ce n-a mers: „{v['title']}”" for v in videos[-2:]],
        "best_titles": [v["title"] for v in top[:5]],
    }


def save_insights(path: Path, insights: dict):
    path.write_text(json.dumps({**insights, "time": time.time()}, ensure_ascii=False, indent=1), encoding="utf-8")
