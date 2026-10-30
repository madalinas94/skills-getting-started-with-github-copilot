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


# ----------------------------------------------------------------- v3: creator tools

from engine import dub, shorts, thumb, tighten  # noqa: E402


def test_jump_cuts_remove_fillers_pauses_and_stumbles():
    words = [[0.1, 0.5, "Salut"], [0.5, 0.9, "ăăă"], [0.9, 1.4, "prieteni!"],
             [3.1, 3.5, "eu"], [3.6, 3.9, "eu"], [3.9, 4.4, "plec."]]
    ranges = tighten.speech_ranges(words, 0, 5.5)
    assert ranges[0] == (0.04, 0.5)            # stops before "ăăă"
    assert ranges[1][0] == 0.9                 # restarts after it
    assert ranges[2][0] >= 3.5                 # first "eu" (stumble) dropped, 1.5 s pause gone
    assert tighten.sound_ranges([(1.0, 2.5)], 0, 4) == [(0, 1.12), (2.44, 4)]


def test_tighten_splits_clip_and_keeps_overlays():
    plan = EditPlan.model_validate({"title": "t", "summary": "s", "tighten": True, "clips": [
        {"media_id": "m1", "start": 0, "end": 6, "keep_audio": True,
         "overlays": [{"text": "a", "start": 0.2}, {"text": "b", "start": 3.7}]}]})
    an = {"m1": {"speech": {"words": [[0.2, 1.0, "unu"], [3.5, 4.2, "doi"]]}}}
    out, removed = tighten.apply(plan, {"m1": {"kind": "video"}}, an)
    assert len(out.clips) == 2 and removed > 2
    assert [o.text for o in out.clips[0].overlays] == ["a"] and [o.text for o in out.clips[1].overlays] == ["b"]
    assert out.clips[1].motion == "close_up"
    again, removed2 = tighten.apply(out, {"m1": {"kind": "video"}}, an)
    assert len(again.clips) == 2 and removed2 == 0   # already tightened pieces are left alone


def test_shorts_heuristic_picks_whole_sentences():
    segs, t = [], 0.0
    for i in range(30):
        text = f"Propoziția numărul {i} are câteva cuvinte în plus" + ("!" if i % 5 == 0 else ".")
        segs.append([round(t, 1), round(t + 3.5, 1), text])
        t += 4.0
    moments = shorts.heuristic({"segments": segs}, 3)
    assert len(moments) == 3
    starts = {s[0] for s in segs}
    for m in moments:
        assert m.start in starts and 20 <= m.end - m.start <= 55
    for a in moments:
        for b in moments:
            assert a is b or a.end <= b.start or b.end <= a.start


def test_dub_units_and_subtitle_mode(tmp_path):
    plan = EditPlan.model_validate({"title": "Vara", "summary": "s", "clips": [
        {"media_id": "m1", "start": 0, "end": 8, "keep_audio": True, "overlays": [{"text": "Salut"}]}]})
    an = {"m1": {"speech": {"words": [[0.2, 0.6, "Bună"], [0.6, 1.0, "ziua."], [2.5, 3.0, "Mergem"], [3.0, 3.4, "acum!"]]}}}
    units = dub.units(plan, an)
    assert [u["text"] for u in units] == ["Bună ziua.", "Mergem acum!"]
    tr = dub.Translation(lines=[dub.Line(id=0, text="Good morning."), dub.Line(id=1, text="Let's go!")],
                         overlays=[dub.Line(id=0, text="Hello")], title="Summer")
    out, extras, _ = dub.build(plan, units, tr, tmp_path, None, None, {}, tmp_path, subtitles_only=True)
    assert out.title == "Summer" and out.clips[0].overlays[0].text == "Hello"
    assert [c.text for c in out.captions] == ["Good morning.", "Let's go!"]
    with pytest.raises(Exception):  # voice dubbing without an ElevenLabs key
        dub.build(plan, units, tr, tmp_path, None, None, {}, tmp_path)


def test_thumbnail_without_person(library, tmp_path):
    d, _media, _by, _an = library
    img = thumb.grab_frame(d / "wide.mp4", 1.0, "video")
    yt, vt = thumb.make(img, "Nu o să-ți vină să crezi", tmp_path / "t")
    from PIL import Image
    assert Image.open(yt).size == (1280, 720) and Image.open(vt).size == (1080, 1920)


def test_creator_render_portrait_broll_sfx_emphasis(library, tmp_path):
    d, _media, by_id, an = library
    plan = EditPlan.model_validate({"title": "t", "summary": "s", "aspect": "9:16", "sfx": True,
                                    "emphasis_zoom": True, "voice_enhance": True, "clips": [
        {"media_id": "m3", "start": 0, "end": 2, "background": "portrait",
         "overlays": [{"text": "Wow", "style": "big_word", "start": 0.2}]},
        {"media_id": "m1", "start": 0, "end": 4, "keep_audio": True, "transition_in": "dissolve",
         "broll": [{"media_id": "m2", "at": 1.0, "duration": 1.5}]}]})
    plan, _ = validate.validate(plan, by_id, an)
    extras, _ = timing.prepare(plan, an, tmp_path / "work", media=by_id, media_dir=d)
    assert extras["sfx"] and any("whoosh" in s["file"] for s in extras["sfx"])
    extras["emphasis"] = [[2.5, 3.4]]
    out = tmp_path / "creator.mp4"
    render.render(plan, by_id, d, tmp_path / "work", out, "preview", extras=extras)
    assert ff.probe(out)["duration"] == pytest.approx(total_length(plan), abs=0.15)


# ----------------------------------------------------------------- v4: pro tools

from engine import colormatch, gpu, multicam, publish, stock, textedit  # noqa: E402


def test_text_cut_removes_words_cleanly():
    plan = EditPlan.model_validate({"title": "t", "summary": "s", "clips": [
        {"media_id": "m1", "start": 0, "end": 6, "keep_audio": True}]})
    an = {"m1": {"speech": {"words": [[0.2, 0.6, "Azi"], [0.7, 1.1, "vorbim"], [1.2, 1.6, "despre"],
                                      [1.7, 2.4, "ceva"], [3.0, 3.6, "important."]]}}}
    t = textedit.transcript(plan, an)
    assert [w[2] for w in t[0]["words"]][:2] == ["Azi", "vorbim"]
    out, n = textedit.cut(plan, an, [{"clip": 0, "s": 1.2, "e": 1.6}, {"clip": 0, "s": 1.7, "e": 2.4}])
    assert n == 2 and [(c.start, c.end) for c in out.clips] == [(0.0, 1.15), (2.7, 6.0)]
    with pytest.raises(ValueError):
        textedit.cut(plan, an, [{"clip": 0, "s": w[0], "e": w[1]} for w in an["m1"]["speech"]["words"]] +
                     [{"clip": 0, "s": 0, "e": 0.2}])


def test_viral_captions_and_emoji():
    plan = EditPlan.model_validate({"title": "t", "summary": "s", "caption_style": "hormozi", "emoji": True,
                                    "clips": [{"media_id": "m1", "start": 0, "end": 4}]})
    words = [[0.1, 0.5, "Am"], [0.5, 1.0, "făcut"], [1.0, 1.6, "bani"], [1.8, 2.6, "incredibil!"]]
    doc = subs.build(plan, 1080, 1920, words)
    assert "hormozi,," in doc and "INCREDIBIL!" in doc and subs.YELLOW in doc
    cues = subs.emoji_cues(words, "hormozi", 1080, 1920)
    assert cues and cues[0]["file"].endswith("1f4b0.png")  # 💰 for "bani"


def test_color_match_lut(tmp_path):
    from PIL import Image
    warm = Image.new("RGB", (64, 64), (230, 140, 60))
    grey = Image.new("RGB", (64, 64), (128, 128, 128))
    table = colormatch.make_lut(warm, [grey], strength=1.0)
    assert table.shape == (33 ** 3, 3)
    mid = table[len(table) // 2]  # around mid-grey input
    assert mid[0] > mid[2]  # pushed towards warm
    cube = colormatch.write_cube(table, tmp_path / "look.cube")
    assert cube.read_text().startswith('TITLE "Montaj look"')


def test_multicam_sync_and_speaker(tmp_path):
    import numpy as np
    sr, T = 8000, 20
    rng = np.random.default_rng(1)
    t = np.arange(T * sr) / sr
    s1, s2, x = np.zeros_like(t), np.zeros_like(t), 0.0
    turns = []
    while x < T:
        d = rng.uniform(2, 4.5)
        turns.append((x, x + d, len(turns) % 2))
        x += d
    for a, b, who in turns:
        m = (t >= a) & (t < b)
        (s1 if who == 0 else s2)[m] += np.sin(2 * np.pi * (220 if who == 0 else 340) * t[m]) * (
            0.5 + 0.5 * np.sign(np.sin(2 * np.pi * rng.uniform(2.5, 5.5) * t[m])))  # speech isn't periodic
    paths = []
    for name, sig, cut in (("a", 0.6 * s1 + 0.15 * s2, 0), ("b", 0.15 * s1 + 0.6 * s2, int(0.9 * sr))):
        raw = tmp_path / f"{name}.raw"
        (np.clip(sig[cut:] + 0.003 * rng.standard_normal(len(sig) - cut), -1, 1) * 32767).astype(np.int16).tofile(raw)
        wav = tmp_path / f"{name}.wav"
        ff.run(["-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", raw, wav])
        paths.append(wav)
    offs = multicam.offsets(paths)
    assert offs[1] == pytest.approx(-0.9, abs=0.05)
    seq = multicam.speakers(paths, offs, 17)
    a0, b0, who = turns[1]
    assert seq[int((a0 + b0) / 2 / 0.5)] == who


def test_stock_queries_and_studio_csv():
    words = [[0, 1, "Astăzi"], [1, 2, "mergem"], [2, 3, "la"], [3, 4, "munte"], [4, 5, "cu"], [5, 6, "bicicleta"]]
    q = stock.queries_from_words(words, 2)
    assert q[0] == "bicicleta" and q[1] in ("astăzi", "mergem") and "la" not in q
    csv_data = ("Content,Video title,Views,Average view duration,Average percentage viewed (%)\n"
                "Total,,1000,0:00:30,40\nabc,Cum am slăbit 10 kg,800,0:00:41,62.5\ndef,Vlog plictisitor,200,0:00:09,12\n").encode()
    vids = publish.parse_studio_csv(csv_data)
    assert [v["title"] for v in vids] == ["Cum am slăbit 10 kg", "Vlog plictisitor"]
    assert vids[0]["avg_view_seconds"] == 41 and vids[0]["avg_percent"] == 62.5
    assert "Cum am slăbit" in publish.basic_insights(vids)["do"][0]
    assert gpu.args("h264_nvenc", "medium", 19)[:2] == ["-c:v", "h264_nvenc"]
    assert gpu.args("libx264", "medium", 19) == ["-c:v", "libx264", "-preset", "medium", "-crf", "19"]
