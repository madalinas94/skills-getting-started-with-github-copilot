"""End-to-end tests on tiny generated media. Run from montaj/:  python -m pytest tests"""

import json
import sys
from pathlib import Path

import anthropic
import httpx2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import agent, analyze, autoplan, export, ff, render, validate  # noqa: E402
from engine.plan import EditPlan, total_length  # noqa: E402

pytestmark = pytest.mark.skipif(not ff.available(), reason="ffmpeg is not installed")


@pytest.fixture(scope="module")
def library(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    ff.run(["-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=6", "-f", "lavfi", "-i", "sine=f=440:d=6",
            "-shortest", "-c:v", "libx264", "-c:a", "aac", d / "wide.mp4"])
    ff.run(["-f", "lavfi", "-i", "testsrc=s=360x640:r=30:d=5", "-c:v", "libx264", d / "tall.mp4"])
    ff.run(["-f", "lavfi", "-i", "gradients=s=800x600:d=1", "-frames:v", "1", d / "photo.png"])
    ff.run(["-f", "lavfi", "-i", "aevalsrc='0.8*sin(2*PI*60*t)*exp(-25*mod(t,0.5))':d=20",
            "-c:a", "libmp3lame", d / "song.mp3"])
    media, by_id = [], {}
    for i, name in enumerate(["wide.mp4", "tall.mp4", "photo.png", "song.mp3"], 1):
        m = ff.probe(d / name)
        m.update(id=f"m{i}", name=name, file=name, role="music" if m["kind"] == "audio" else "material")
        media.append(m)
        by_id[m["id"]] = m
    frames = d / "frames"
    an = {m["id"]: analyze.analyze(m, d / m["file"], frames, 3) for m in media}
    return d, media, by_id, an


def test_probe_kinds(library):
    _d, media, _by, _an = library
    assert [m["kind"] for m in media] == ["video", "video", "image", "audio"]
    assert media[0]["has_audio"] and not media[1]["has_audio"]
    assert media[1]["height"] > media[1]["width"]


def test_beats_found(library):
    _d, _media, _by, an = library
    beats = an["m4"]["beats"]
    assert beats["bpm"] == pytest.approx(120, abs=2)
    gaps = [b - a for a, b in zip(beats["beats"], beats["beats"][1:])]
    assert all(abs(g - 0.5) < 0.03 for g in gaps)


def test_auto_plan_renders(library, tmp_path):
    d, media, by_id, an = library
    plan = autoplan.build(media, an, {"preset": "travel", "title": "Țară și mare", "duration": 12})
    plan, issues = validate.validate(plan, by_id, an)
    assert plan.clips and plan.music
    out = tmp_path / "out.mp4"
    info = render.render(plan, by_id, d, tmp_path / "work", out, "preview")
    probe = ff.probe(out)
    assert probe["duration"] == pytest.approx(info["duration"], abs=0.15)
    assert probe["duration"] == pytest.approx(total_length(plan), abs=0.15)
    assert (probe["width"], probe["height"]) == (info["width"], info["height"])
    assert probe["has_audio"]

    render.export_mp3(out, tmp_path / "a.mp3")
    jpg, png = render.export_cover(plan, by_id, d, tmp_path / "work", tmp_path / "cover", "preview")
    assert jpg.stat().st_size > 1000 and png.stat().st_size > 1000
    assert "<fcpxml" in export.fcpxml(plan, by_id, d)
    assert "FROM CLIP NAME" in export.edl(plan, by_id)
    assert "Țară și mare" in export.srt(plan)


def test_every_transition_look_and_motion(library, tmp_path):
    d, _media, by_id, an = library
    clips = []
    looks = list(render.LOOKS)
    for i, t in enumerate(["cut", "dissolve", "zoomin", "fadeblack", "smoothleft", "wipeleft"]):
        clips.append({"media_id": ["m1", "m2", "m3"][i % 3], "start": 0.5, "end": 2.0,
                      "transition_in": t, "motion": ["zoom_in", "pan_left", "punch_in", "zoom_out", "pan_right", "none"][i],
                      "fit": ["fill", "blur_bg", "fit"][i % 3], "speed": [1, 1.5, 1, 0.75, 1, 1][i],
                      "color": {"look": looks[i % len(looks)], "warmth": 0.4, "vignette": i % 2 == 0},
                      "overlays": [{"text": "Salut, lume! 100% „real”", "style": s, "start": 0.1, "duration": 1}
                                   for s in ("title", "caption", "lower_third", "label", "big_word")][i % 5: i % 5 + 1]})
    plan = EditPlan.model_validate({"title": "Test", "summary": "s", "aspect": "1:1", "clips": clips,
                                    "music": {"media_id": "m4", "duck": True},
                                    "captions": [{"start": 0.5, "end": 2, "text": "O subtitrare: cu două puncte"}]})
    plan, _ = validate.validate(plan, by_id, an)
    out = tmp_path / "all.mp4"
    render.render(plan, by_id, d, tmp_path / "work", out, "preview")
    assert ff.probe(out)["duration"] == pytest.approx(total_length(plan), abs=0.15)


def test_validate_repairs(library):
    _d, _media, by_id, an = library
    plan = EditPlan.model_validate({"title": "x", "summary": "x", "clips": [
        {"media_id": "nope", "start": 0, "end": 2},
        {"media_id": "m1", "start": 4, "end": 99, "speed": 9, "transition_in": "dissolve"},
        {"media_id": "m4", "start": 0, "end": 2},
    ]})
    fixed, issues = validate.validate(plan, by_id, an)
    assert len(fixed.clips) == 1
    c = fixed.clips[0]
    assert c.end <= by_id["m1"]["duration"] and c.speed == 4.0 and c.transition_in == "cut"
    assert len(issues) >= 3


def test_ai_request_and_parse(library, monkeypatch):
    d, media, by_id, an = library
    seen = {}
    reply = {"title": "Plan AI", "summary": "Hook, apoi detalii.", "aspect": "9:16", "fps": 30,
             "clips": [{"media_id": "m2", "start": 1, "end": 3, "reason": "Cadrul cel mai clar"},
                       {"media_id": "m3", "start": 0, "end": 2, "motion": "zoom_in", "transition_in": "dissolve"}],
             "music": {"media_id": "m4"}, "snap_to_beat": True}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta")
        return httpx2.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": json.dumps(reply)}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 10}})

    fake = anthropic.Anthropic(api_key="test", http_client=anthropic.DefaultHttpxClient(
        transport=httpx2.MockTransport(handler)))
    monkeypatch.setattr(agent, "client_for", lambda key: fake)

    plan = agent.plan_edit(media, an, d / "frames", {"preset": "reels", "rules": "Fără poze tremurate"},
                           "test", "claude-sonnet-5-5", "medium")
    body = seen["body"]
    assert body["model"] == "claude-sonnet-5-5"
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["fallbacks"] == "default" and seen["beta"] == "server-side-fallback-2026-07-01"
    content = body["messages"][0]["content"]
    images = [b for b in content if b["type"] == "image"]
    assert len(images) == 3 + 3 + 1  # 3 frames per video + the photo
    assert any("cache_control" in b for b in content)
    assert "Fără poze tremurate" in content[-1]["text"]

    fixed, _ = validate.validate(plan, by_id, an)
    assert [c.media_id for c in fixed.clips] == ["m2", "m3"]
    assert fixed.clips[0].reason == "Cadrul cel mai clar"


# ----------------------------------------------------------------- v2 features

from engine import styles, subs, timing  # noqa: E402

try:
    from engine import vision  # noqa: E402
except ImportError:
    vision = None


def test_karaoke_and_animated_text():
    plan = EditPlan.model_validate({"title": "t", "summary": "s", "caption_style": "karaoke", "clips": [
        {"media_id": "m1", "start": 0, "end": 3, "overlays": [
            {"text": "Salut {lume} \\N", "animation": a, "start": 0, "duration": 1} for a in
            ("pop", "slide_up", "typewriter", "zoom_out", "fade", "none")]}]})
    words = [[0.1, 0.4, "Bună"], [0.4, 0.8, "ziua,"], [1.5, 1.9, "prieteni!"]]
    doc = subs.build(plan, 1080, 1920, words)
    assert "{lume}" not in doc and "(lume)" in doc  # user braces can't inject ASS tags
    assert doc.count("karaoke,,") == 3  # one event per spoken word
    assert "\\c&H004DE1FF" in doc  # active word highlighted
    assert "\\move(" in doc and "\\alpha&HFF&" in doc and "\\fscx30" in doc
    assert subs.group_words(words, True) == [words[:2], words[2:]]  # broken after the comma


def test_clip_words_follow_trim_and_speed():
    an = {"m1": {"speech": {"words": [[1.0, 1.4, "a"], [5.0, 5.5, "b"], [9.0, 9.2, "outside"]]}}}
    plan = EditPlan.model_validate({"title": "t", "summary": "s", "caption_style": "clean", "clips": [
        {"media_id": "m1", "start": 0.5, "end": 2.5, "keep_audio": True},
        {"media_id": "m1", "start": 4.0, "end": 6.0, "speed": 2.0, "keep_audio": True}]})
    words = timing.clip_words(plan, an)
    assert words == [[0.5, 0.9, "a"], [2.5, 2.75, "b"]]


def test_styles_roundtrip(tmp_path):
    plan = EditPlan.model_validate({"title": "Vara", "summary": "s", "beat_fx": "zoom", "clips": [
        {"media_id": "m1", "start": 0, "end": 2, "color": {"look": "warm"}},
        {"media_id": "m1", "start": 2, "end": 5, "color": {"look": "warm"}, "transition_in": "dissolve"}]})
    lib = styles.Library(tmp_path / "styles.json")
    st = lib.add(styles.derive(plan, "Vara mea"))
    assert st["look"] == "warm" and st["pace"] == 2.5 and st["beat_fx"] == "zoom"
    eff = styles.resolve({"style_id": st["id"], "preset": "vlog"}, lib)
    assert eff["look"] == "warm" and eff["label"] == "Vara mea"
    lib.delete(st["id"])
    assert lib.all() == []


def test_music_ends_with_video(library):
    _d, _media, by_id, an = library
    plan = EditPlan.model_validate({"title": "t", "summary": "s", "clips": [
        {"media_id": "m1", "start": 0, "end": 4}], "music": {"media_id": "m4", "align_end": True}})
    plan, _ = validate.validate(plan, by_id, an)
    song = by_id["m4"]["duration"]
    assert abs(plan.music.start + total_length(plan) - song) <= 0.26  # within half a beat
    assert timing.beat_grid(plan, an)["period"] == pytest.approx(0.5, abs=0.02)


def test_beat_fx_voice_and_tracking_render(library, tmp_path):
    d, _media, by_id, an = library
    vo = tmp_path / "vo.mp3"
    ff.run(["-f", "lavfi", "-i", "sine=f=300:d=1.5", vo])
    plan = EditPlan.model_validate({"title": "t", "summary": "s", "aspect": "9:16", "beat_fx": "mix",
                                    "beat_fx_every": 1, "caption_style": "karaoke", "clips": [
        {"media_id": "m1", "start": 0, "end": 3, "fit": "track"},
        {"media_id": "m3", "start": 0, "end": 2, "fit": "track", "transition_in": "dissolve"}],
        "music": {"media_id": "m4"}})
    plan, _ = validate.validate(plan, by_id, an)
    extras = {"beat": timing.beat_grid(plan, an), "words": [[0.2, 0.6, "Test"], [0.6, 1.0, "unu"]],
              "voice": [{"file": str(vo), "start": 1.0, "duration": 1.5}],
              "faces": {"m1": [[0, 0.2, 0.5], [3, 0.8, 0.5]], "m3": [[0, 0.5, 0.4]]}}
    out = tmp_path / "fx.mp4"
    render.render(plan, by_id, d, tmp_path / "work", out, "preview", extras=extras)
    assert ff.probe(out)["duration"] == pytest.approx(total_length(plan), abs=0.15)


@pytest.mark.skipif(vision is None, reason="numpy missing")
def test_quality_flags_shaky_footage(tmp_path):
    shaky = tmp_path / "shaky.mp4"
    ff.run(["-f", "lavfi", "-i", "testsrc=s=1280x720:r=30:d=4",
            "-vf", "crop=1000:560:x='140+60*random(1)*between(t,1,3)':y='80+40*random(2)*between(t,1,3)',scale=1280:720",
            "-c:v", "libx264", shaky])
    steady = tmp_path / "steady.mp4"
    ff.run(["-f", "lavfi", "-i", "testsrc=s=1280x720:r=30:d=4", "-c:v", "libx264", steady])
    rs = vision.scan(shaky, ff.probe(shaky))
    rq = vision.scan(steady, ff.probe(steady))
    assert any(i["kind"] == "shaky" for i in rs["issues"])
    assert not any(i["kind"] == "shaky" for i in rq["issues"])


def test_review_and_copy_requests(library, monkeypatch, tmp_path):
    d, media, _by, an = library
    replies = [
        {"score": 6, "verdict": "Hook slab", "problems": ["Începutul e lent"], "fixes": "Start with clip 2"},
        {"hooks": ["a", "b", "c"], "posts": [{"platform": "TikTok", "caption": "x", "hashtags": ["vara"]}],
         "youtube_title": "T", "best_time": "seara"},
    ]
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx2.Response(200, json={
            "id": "msg", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": json.dumps(replies[len(seen) - 1])}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}})

    fake = anthropic.Anthropic(api_key="t", http_client=anthropic.DefaultHttpxClient(
        transport=httpx2.MockTransport(handler)))
    monkeypatch.setattr(agent, "client_for", lambda key: fake)
    frame = tmp_path / "f.jpg"
    analyze.extract_frame(d / "wide.mp4", 1.0, frame)
    plan = EditPlan.model_validate({"title": "t", "summary": "s", "clips": [{"media_id": "m1", "start": 0, "end": 2}]})
    review = agent.review_preview([(1.0, frame)], plan, {"rules": "scurt"}, "t")
    assert review.score == 6 and seen[0]["system"].startswith("You are a demanding")
    copy = agent.social_copy([(1.0, frame)], plan, {}, "t")
    assert "#vara" in export.post_text(copy)
