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
