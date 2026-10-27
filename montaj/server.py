"""Montaj — local web app for the video editing agent.

Run:  python server.py   then open http://127.0.0.1:8765
"""

import json
import os
import re
import shutil
import threading
import time
import traceback
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import agent, analyze, autoplan, export, ff, presets, render, speech, styles, timing, validate
from engine.plan import ASPECT_SIZE, EditPlan, timeline, total_length

try:
    from engine import vision
except ImportError:
    vision = None

ROOT = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("MONTAJ_WORKSPACE", ROOT / "workspace"))
PROJECTS = WORKSPACE / "projects"
SETTINGS_FILE = WORKSPACE / "settings.json"
LIBRARY = styles.Library(WORKSPACE / "styles.json")
FRAMES_PER_VIDEO = 5
REVIEW_TARGET = 8
REVIEW_ROUNDS = 2
PROJECTS.mkdir(parents=True, exist_ok=True)

VARIANTS = [
    {"label": "Dinamic", "preset": "reels",
     "hint": "Fast and energetic: short shots on the beat, punchy animated text, beat effects."},
    {"label": "Cinematic", "preset": "cinematic",
     "hint": "Slow and elegant: wider shots, smooth transitions, cinematic grade, few words on screen."},
    {"label": "Scurt (15s)", "preset": None, "duration": 15,
     "hint": "A 15-second teaser: only the very best moments, strongest hook first."},
]

app = FastAPI(title="Montaj")
_lock = threading.RLock()
_jobs: dict = {}


# ----------------------------------------------------------------- storage

def load_settings() -> dict:
    data = {"api_key": "", "model": agent.DEFAULT_MODEL, "effort": "medium",
            "eleven_key": "", "eleven_voice": "", "whisper_model": "small"}
    if SETTINGS_FILE.exists():
        data.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    os.environ["MONTAJ_WHISPER_MODEL"] = data["whisper_model"]
    return data


def api_key() -> str | None:
    return load_settings().get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or None


def eleven_key() -> str | None:
    return load_settings().get("eleven_key") or os.environ.get("ELEVENLABS_API_KEY") or None


def pdir(pid: str) -> Path:
    if not re.fullmatch(r"[a-z0-9]{8,32}", pid):
        raise HTTPException(404, "Proiect inexistent")
    d = PROJECTS / pid
    if not (d / "project.json").exists():
        raise HTTPException(404, "Proiect inexistent")
    return d


def load(pid: str) -> dict:
    with _lock:
        return json.loads((pdir(pid) / "project.json").read_text(encoding="utf-8"))


def save(project: dict):
    with _lock:
        path = PROJECTS / project["id"] / "project.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(project, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)


def update(pid: str, fn):
    """Read-modify-write a project under the lock."""
    with _lock:
        project = load(pid)
        fn(project)
        save(project)
        return project


DEFAULT_SETTINGS = {"preset": presets.DEFAULT, "style_id": "", "aspect": "", "duration": 30, "rules": "",
                    "title": "", "outro": "", "caption_style": "", "beat_fx": "", "auto_color": True,
                    "music_align": True, "self_review": True, "voiceover": False, "voiceover_text": ""}


def new_project(name: str) -> dict:
    pid = uuid.uuid4().hex[:12]
    d = PROJECTS / pid
    for sub in ("media", "frames", "thumbs", "work", "exports"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    project = {
        "id": pid, "name": name or "Proiect nou", "created": time.time(),
        "media": [], "analysis": {}, "plan": None, "issues": [], "history": [], "chat": [],
        "settings": dict(DEFAULT_SETTINGS), "preview": None, "exports": [], "variants": [],
        "review": None, "social": None,
    }
    save(project)
    return project


def media_map(project: dict, roles=("material", "music")) -> dict:
    return {m["id"]: m for m in project["media"] if m["role"] in roles}


def style_of(project: dict) -> dict:
    return styles.resolve(project["settings"], LIBRARY)


# ----------------------------------------------------------------- jobs

def start_job(pid: str, kind: str, fn) -> dict:
    with _lock:
        for job in _jobs.values():
            if job["project"] == pid and job["status"] == "running":
                raise HTTPException(409, "Agentul lucrează deja la acest proiect. Așteaptă să termine.")
        job = {"id": uuid.uuid4().hex[:12], "project": pid, "kind": kind, "status": "running",
               "progress": 0.0, "message": "Pornesc…", "log": [], "error": None, "started": time.time()}
        _jobs[job["id"]] = job

    def step(progress=None, message=None):
        if progress is not None:
            job["progress"] = round(max(job["progress"], min(1.0, progress)), 3)
        if message and message != job["message"]:
            job["message"] = message
            job["log"].append({"t": round(time.time() - job["started"], 1), "text": message})

    def runner():
        try:
            fn(step)
            step(1.0, "Gata")
            job["status"] = "done"
            job["progress"] = 1.0
        except Exception as exc:  # surfaced to the UI
            traceback.print_exc()
            job["status"] = "error"
            job["error"] = agent.describe_error(exc)
            job["log"].append({"t": round(time.time() - job["started"], 1), "text": "Eroare: " + job["error"]})

    threading.Thread(target=runner, daemon=True).start()
    return job


def running_job(pid: str):
    return next((j for j in _jobs.values() if j["project"] == pid and j["status"] == "running"), None)


def ensure_analysis(pid: str, step, lo=0.0, hi=0.3):
    project = load(pid)
    d = pdir(pid)
    todo = [m for m in project["media"] if m["id"] not in project["analysis"]]
    for i, m in enumerate(todo):
        what = "ritm și energie" if m["kind"] == "audio" else "cadre, scene, lumină, fețe, tremurat" + (
            ", vorbire" if m.get("has_audio") and speech.available() else "")
        step(lo + (hi - lo) * i / max(1, len(todo)), f"Analizez {m['name']} ({what})")
        info = analyze.analyze(m, d / "media" / m["file"], d / "frames", FRAMES_PER_VIDEO)
        if m["role"] == "example":
            info["style"] = analyze.style_fingerprint(m, info)
        update(pid, lambda p: p["analysis"].__setitem__(m["id"], info) if any(
            x["id"] == m["id"] for x in p["media"]) else None)
    step(hi, "Analiza e gata")
    return load(pid)


def set_plan(pid: str, plan: EditPlan, issues: list, label: str):
    def fn(p):
        if p["plan"]:
            p["history"] = (p["history"] + [{"plan": p["plan"], "label": p.get("plan_label", ""),
                                             "time": time.time()}])[-20:]
        p["plan"] = plan.model_dump()
        p["plan_label"] = label
        p["issues"] = issues
    update(pid, fn)


def make_plan(project: dict, settings: dict, use_ai: bool, style: dict) -> tuple:
    """Plan (AI or automatic) + validation. Returns (plan, issues)."""
    d = pdir(project["id"])
    material = [m for m in project["media"] if m["role"] in ("material", "music")]
    if use_ai:
        s = load_settings()
        visible = [m for m in project["media"] if m["role"] in ("material", "music", "example")]
        plan = agent.plan_edit(visible, project["analysis"], d / "frames", settings, api_key(),
                               s["model"], s["effort"], style)
    else:
        plan = autoplan.build(material, project["analysis"], settings, style)
    plan, issues = validate.validate(plan, media_map(project), project["analysis"])
    if not plan.clips:
        raise RuntimeError("Planul nu are clipuri valide. " + " ".join(issues))
    return plan, issues


def render_plan(project: dict, plan: EditPlan, out: Path, quality: str, step, lo: float, hi: float):
    """Prepare extras (voice-over, captions, beats, faces) and render. Returns (info, issues)."""
    d = pdir(project["id"])
    s = load_settings()
    extras, issues = timing.prepare(plan, project["analysis"], d / "work", eleven_key(),
                                    s.get("eleven_voice") or None,
                                    lambda msg: step(lo, msg))
    info = render.render(plan, media_map(project), d / "media", d / "work", out, quality,
                         lambda p, msg="": step(lo + (hi - lo) * p, msg or None), extras)
    return info, issues


def render_preview(pid: str, step, lo: float, hi: float = 1.0):
    project = load(pid)
    d = pdir(pid)
    plan = EditPlan.model_validate(project["plan"])
    name = f"preview_{int(time.time() * 1000)}.mp4"
    info, issues = render_plan(project, plan, d / "work" / name, "preview", step, lo, hi)

    def fn(p):
        old = p.get("preview")
        p["preview"] = {"file": f"work/{name}", **info, "time": time.time()}
        p["issues"] = [i for i in p.get("issues", []) if i not in issues] + issues
        if old and old.get("file") and old["file"] != p["preview"]["file"] and "variant" not in old["file"]:
            (d / old["file"]).unlink(missing_ok=True)
    update(pid, fn)


def preview_frames(pid: str, count: int = 8):
    """Frames from the current preview: [(timeline_seconds, path)]."""
    project = load(pid)
    d = pdir(pid)
    video = d / project["preview"]["file"]
    total = project["preview"]["duration"]
    out_dir = d / "work" / "review"
    out_dir.mkdir(exist_ok=True)
    frames = []
    for i in range(count):
        t = total * (i + 0.5) / count
        path = out_dir / f"r{i}.jpg"
        analyze.extract_frame(video, t, path, width=480)
        frames.append((t, path))
    return frames


def self_review(pid: str, step, lo: float, hi: float):
    """The agent watches its own draft, scores it, and fixes it (up to REVIEW_ROUNDS times)."""
    s = load_settings()
    span = (hi - lo) / REVIEW_ROUNDS
    for rnd in range(1, REVIEW_ROUNDS + 1):
        base = lo + span * (rnd - 1)
        project = load(pid)
        plan = EditPlan.model_validate(project["plan"])
        step(base, f"Agentul își verifică montajul (runda {rnd})")
        review = agent.review_preview(preview_frames(pid), plan, project["settings"], api_key(),
                                      s["model"], s["effort"], style_of(project))
        record = {**review.model_dump(), "round": rnd, "time": time.time()}
        update(pid, lambda p: (p.__setitem__("review", record),
                               p["chat"].append({"role": "agent", "time": time.time(),
                                                 "text": f"Auto-verificare {rnd}: {review.score}/10 — {review.verdict}"})))
        if review.score >= REVIEW_TARGET or rnd == REVIEW_ROUNDS:
            return
        step(base + span * 0.3, f"Nota {review.score}/10 — repar: {'; '.join(review.problems[:2])}")
        d = pdir(pid)
        visible = [m for m in project["media"] if m["role"] in ("material", "music", "example")]
        fixed = agent.revise_edit(visible, project["analysis"], d / "frames", project["settings"], plan,
                                  review.fixes + "\n" + "\n".join(review.problems), api_key(),
                                  s["model"], s["effort"], style_of(project))
        fixed, issues = validate.validate(fixed, media_map(project), project["analysis"])
        set_plan(pid, fixed, issues, f"Auto-corectat (runda {rnd})")
        render_preview(pid, step, base + span * 0.5, base + span)


# ----------------------------------------------------------------- API: app

@app.get("/api/status")
def status():
    s = load_settings()
    return {
        "ffmpeg": ff.available(),
        "has_key": bool(api_key()),
        "key_from_env": bool(os.environ.get("ANTHROPIC_API_KEY")) and not s.get("api_key"),
        "has_eleven": bool(eleven_key()),
        "eleven_voice": s.get("eleven_voice", ""),
        "whisper": speech.available(), "whisper_model": s["whisper_model"],
        "faces": bool(vision and vision.faces_available()), "quality": vision is not None,
        "model": s["model"], "effort": s["effort"],
        "models": agent.MODELS,
        "presets": {k: {"label": v["label"], "aspect": v["aspect"], "duration": v["duration"],
                        "brief": v["brief"]} for k, v in presets.PRESETS.items()},
        "styles": LIBRARY.all(),
    }


class SettingsIn(BaseModel):
    api_key: str | None = None
    model: str | None = None
    effort: str | None = None
    eleven_key: str | None = None
    eleven_voice: str | None = None
    whisper_model: str | None = None


@app.post("/api/settings")
def save_settings(body: SettingsIn):
    s = load_settings()
    if body.api_key is not None:
        s["api_key"] = body.api_key.strip()
    if body.eleven_key is not None:
        s["eleven_key"] = body.eleven_key.strip()
    if body.eleven_voice is not None:
        s["eleven_voice"] = body.eleven_voice.strip()
    if body.model in agent.MODELS:
        s["model"] = body.model
    if body.effort in ("low", "medium", "high", "xhigh", "max"):
        s["effort"] = body.effort
    if body.whisper_model in ("tiny", "base", "small", "medium", "large-v3"):
        s["whisper_model"] = body.whisper_model
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(s, indent=1), encoding="utf-8")
    return status()


# ----------------------------------------------------------------- API: projects

@app.get("/api/projects")
def list_projects():
    out = []
    for d in PROJECTS.iterdir():
        f = d / "project.json"
        if f.exists():
            p = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": p["id"], "name": p["name"], "created": p["created"],
                        "media": len(p["media"]), "has_plan": bool(p["plan"])})
    return sorted(out, key=lambda p: -p["created"])


class NameIn(BaseModel):
    name: str = ""


@app.post("/api/projects")
def create_project(body: NameIn):
    return new_project(body.name.strip())


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    project = load(pid)
    project["settings"] = {**DEFAULT_SETTINGS, **project["settings"]}
    for key in ("variants", "review", "social"):
        project.setdefault(key, None if key != "variants" else [])
    project["running"] = running_job(pid)
    if project["plan"]:
        tl = timeline(EditPlan.model_validate(project["plan"]))
        project["timeline"] = [{"start": s, "length": l} for _c, s, l in tl]
    return project


@app.patch("/api/projects/{pid}")
def rename_project(pid: str, body: NameIn):
    return update(pid, lambda p: p.__setitem__("name", body.name.strip() or p["name"]))


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    shutil.rmtree(pdir(pid))
    return {"ok": True}


SAFE = re.compile(r"[^A-Za-z0-9._ ăâîșțĂÂÎȘȚ-]+")


@app.post("/api/projects/{pid}/media")
async def upload(pid: str, files: list[UploadFile] = File(...), role: str = Form("material")):
    d = pdir(pid)
    added, errors = [], []
    for up in files:
        mid = "m" + uuid.uuid4().hex[:6]
        clean = SAFE.sub("_", Path(up.filename or "fisier").name)[:80] or "fisier"
        fname = f"{mid}_{clean}"
        dest = d / "media" / fname
        with dest.open("wb") as out:
            while chunk := await up.read(1 << 20):
                out.write(chunk)
        try:
            info = ff.probe(dest)
        except ff.FFmpegError as exc:
            dest.unlink(missing_ok=True)
            errors.append(f"{up.filename}: {exc}")
            continue
        r = role if role in ("material", "example", "music") else "material"
        if info["kind"] == "audio":
            r = "music"
        elif r == "music":
            r = "material"
        m = {"id": mid, "name": up.filename, "file": fname, "role": r, **info, "thumb": None}
        if info["kind"] in ("video", "image"):
            try:
                analyze.thumbnail(m, dest, d / "thumbs" / f"{mid}.jpg")
                m["thumb"] = f"thumbs/{mid}.jpg"
            except ff.FFmpegError:
                pass
        added.append(m)
    update(pid, lambda p: p["media"].extend(added))
    job = None
    if added and not running_job(pid):  # analyse right away so quality badges show up
        job = start_job(pid, "analyze", lambda step: ensure_analysis(pid, step, 0.0, 1.0))
    return {"project": get_project(pid), "errors": errors, "job": job}


class RoleIn(BaseModel):
    role: str


@app.patch("/api/projects/{pid}/media/{mid}")
def set_role(pid: str, mid: str, body: RoleIn):
    def fn(p):
        for m in p["media"]:
            if m["id"] == mid:
                if body.role == "music" and m["kind"] != "audio" and not m.get("has_audio"):
                    raise HTTPException(400, "Fișierul nu are sunet.")
                m["role"] = body.role if body.role in ("material", "example", "music") else m["role"]
                p["analysis"].pop(mid, None)  # examples get a style fingerprint
    update(pid, fn)
    return get_project(pid)


@app.delete("/api/projects/{pid}/media/{mid}")
def delete_media(pid: str, mid: str):
    d = pdir(pid)

    def fn(p):
        m = next((m for m in p["media"] if m["id"] == mid), None)
        if not m:
            raise HTTPException(404, "Fișier inexistent")
        (d / "media" / m["file"]).unlink(missing_ok=True)
        p["media"] = [x for x in p["media"] if x["id"] != mid]
        p["analysis"].pop(mid, None)
    update(pid, fn)
    return get_project(pid)


class ProjectSettings(BaseModel):
    preset: str = presets.DEFAULT
    style_id: str = ""
    aspect: str = ""
    duration: float = 30
    rules: str = ""
    title: str = ""
    outro: str = ""
    caption_style: str = ""
    beat_fx: str = ""
    auto_color: bool = True
    music_align: bool = True
    self_review: bool = True
    voiceover: bool = False
    voiceover_text: str = ""


@app.put("/api/projects/{pid}/settings")
def put_settings(pid: str, body: ProjectSettings):
    update(pid, lambda p: p.__setitem__("settings", body.model_dump()))
    return {"ok": True}


# ----------------------------------------------------------------- API: the agent

class GenerateIn(BaseModel):
    mode: str = "ai"  # "ai" or "auto"


def _check_ready(project: dict, use_ai: bool):
    if not any(m["role"] == "material" and m["kind"] in ("video", "image") for m in project["media"]):
        raise HTTPException(400, "Încarcă cel puțin un video sau o poză.")
    if use_ai and not api_key():
        raise HTTPException(400, "Lipsește cheia API Anthropic. Adaug-o în Setări sau folosește modul automat.")


@app.post("/api/projects/{pid}/generate")
def generate(pid: str, body: GenerateIn):
    use_ai = body.mode == "ai"
    _check_ready(load(pid), use_ai)

    def work(step):
        project = ensure_analysis(pid, step, 0.0, 0.25)
        style = style_of(project)
        if use_ai:
            s = load_settings()
            step(0.27, f"Agentul AI se uită la cadre și scrie planul ({agent.MODELS.get(s['model'], s['model'])})")
        else:
            step(0.27, "Construiesc planul automat (fără AI)")
        plan, issues = make_plan(project, project["settings"], use_ai, style)
        step(0.4, "Validez planul pe fișierele reale")
        set_plan(pid, plan, issues, "AI" if use_ai else "Automat")
        update(pid, lambda p: (p["chat"].append({"role": "agent", "text": plan.summary, "time": time.time()}),
                               p.__setitem__("review", None)))
        review = use_ai and project["settings"].get("self_review", True)
        render_preview(pid, step, 0.42, 0.62 if review else 1.0)
        if review:
            self_review(pid, step, 0.62, 1.0)

    return start_job(pid, "generate", work)


@app.post("/api/projects/{pid}/variants")
def make_variants(pid: str, body: GenerateIn):
    use_ai = body.mode == "ai"
    _check_ready(load(pid), use_ai)

    def work(step):
        project = ensure_analysis(pid, step, 0.0, 0.2)
        base = {**DEFAULT_SETTINGS, **project["settings"]}
        aspect = base["aspect"] or style_of(project)["aspect"]
        jobs = []
        for v in VARIANTS:
            st = {**base, "aspect": aspect, "variant": v["hint"], "style_id": ""}
            if v.get("preset"):
                st["preset"] = v["preset"]
                st["duration"] = presets.get(v["preset"])["duration"] if not base.get("duration") else base["duration"]
            if v.get("duration"):
                st["duration"] = v["duration"]
            jobs.append((v, st, styles.resolve(st, LIBRARY) if not v.get("preset") else presets.get(v["preset"])))
        step(0.22, "Agentul face 3 variante în paralel" if use_ai else "Construiesc 3 variante")
        with ThreadPoolExecutor(max_workers=3) as pool:
            plans = list(pool.map(lambda j: make_plan(project, j[1], use_ai, j[2]), jobs))
        d = pdir(pid)
        out = []
        for k, ((v, st, _style), (plan, issues)) in enumerate(zip(jobs, plans)):
            lo = 0.45 + 0.55 * k / len(jobs)
            step(lo, f"Randez varianta „{v['label']}”")
            name = f"variant_{k}_{int(time.time() * 1000)}.mp4"
            info, more = render_plan(project, plan, d / "work" / name, "preview", step,
                                     lo, lo + 0.55 / len(jobs))
            out.append({"label": v["label"], "plan": plan.model_dump(), "issues": issues + more,
                        "preview": {"file": f"work/{name}", **info}})
        update(pid, lambda p: p.__setitem__("variants", out))

    return start_job(pid, "variants", work)


class ChooseIn(BaseModel):
    index: int


@app.post("/api/projects/{pid}/variants/choose")
def choose_variant(pid: str, body: ChooseIn):
    project = load(pid)
    variants = project.get("variants") or []
    if not 0 <= body.index < len(variants):
        raise HTTPException(404, "Variantă inexistentă")
    v = variants[body.index]
    set_plan(pid, EditPlan.model_validate(v["plan"]), v["issues"], f"Varianta {v['label']}")
    update(pid, lambda p: (p.__setitem__("preview", {**v["preview"], "time": time.time()}),
                           p["chat"].append({"role": "agent", "time": time.time(),
                                             "text": f"Ai ales varianta „{v['label']}”. {v['plan']['summary']}"})))
    return get_project(pid)


class ReviseIn(BaseModel):
    feedback: str


@app.post("/api/projects/{pid}/revise")
def revise(pid: str, body: ReviseIn):
    project = load(pid)
    if not project["plan"]:
        raise HTTPException(400, "Generează întâi un montaj.")
    if not api_key():
        raise HTTPException(400, "Revizia prin chat are nevoie de cheia API Anthropic (Setări).")
    feedback = body.feedback.strip()
    if not feedback:
        raise HTTPException(400, "Scrie ce vrei să schimbe agentul.")
    update(pid, lambda p: p["chat"].append({"role": "user", "text": feedback, "time": time.time()}))

    def work(step):
        project = ensure_analysis(pid, step, 0.0, 0.1)
        d = pdir(pid)
        s = load_settings()
        step(0.12, "Agentul reface planul după cerința ta")
        visible = [m for m in project["media"] if m["role"] in ("material", "music", "example")]
        plan = agent.revise_edit(visible, project["analysis"], d / "frames", project["settings"],
                                 EditPlan.model_validate(project["plan"]), feedback, api_key(),
                                 s["model"], s["effort"], style_of(project))
        plan, issues = validate.validate(plan, media_map(project), project["analysis"])
        set_plan(pid, plan, issues, "Revizie: " + feedback[:40])
        update(pid, lambda p: p["chat"].append({"role": "agent", "text": plan.summary, "time": time.time()}))
        render_preview(pid, step, 0.4)

    return start_job(pid, "revise", work)


@app.post("/api/projects/{pid}/review")
def review_now(pid: str):
    project = load(pid)
    if not project.get("preview"):
        raise HTTPException(400, "Generează întâi un montaj.")
    if not api_key():
        raise HTTPException(400, "Auto-verificarea are nevoie de cheia API Anthropic (Setări).")
    return start_job(pid, "review", lambda step: self_review(pid, step, 0.0, 1.0))


class PlanIn(BaseModel):
    plan: dict
    render: bool = True


@app.put("/api/projects/{pid}/plan")
def put_plan(pid: str, body: PlanIn):
    project = load(pid)
    try:
        plan = EditPlan.model_validate(body.plan)
    except Exception as exc:
        raise HTTPException(400, f"Plan invalid: {exc}")
    plan, issues = validate.validate(plan, media_map(project), project["analysis"])
    if not plan.clips:
        raise HTTPException(400, "Planul trebuie să aibă cel puțin un clip.")
    set_plan(pid, plan, issues, "Editare manuală")
    if body.render:
        return {"job": start_job(pid, "preview", lambda step: render_preview(pid, step, 0.0))}
    return {"job": None}


@app.post("/api/projects/{pid}/undo")
def undo(pid: str):
    def fn(p):
        if not p["history"]:
            raise HTTPException(400, "Nu mai am versiuni anterioare.")
        last = p["history"].pop()
        p["plan"], p["plan_label"] = last["plan"], last.get("label", "")
        p["issues"] = []
    update(pid, fn)
    return {"job": start_job(pid, "preview", lambda step: render_preview(pid, step, 0.0))}


# ----------------------------------------------------------------- API: styles

class StyleIn(BaseModel):
    name: str = ""


@app.post("/api/projects/{pid}/styles")
def save_style(pid: str, body: StyleIn):
    project = load(pid)
    if not project["plan"]:
        raise HTTPException(400, "Generează întâi un montaj.")
    style = styles.derive(EditPlan.model_validate(project["plan"]), body.name.strip())
    style["base_preset"] = project["settings"].get("preset")
    LIBRARY.add(style)
    return status()


@app.delete("/api/styles/{sid}")
def delete_style(sid: str):
    LIBRARY.delete(sid)
    return status()


# ----------------------------------------------------------------- API: export

class ExportIn(BaseModel):
    quality: str = "1080p"
    formats: list[str] = []


def reframe(plan: EditPlan, aspect: str, media: dict, analysis: dict) -> EditPlan:
    """Same edit in another aspect ratio; shots with people follow the face."""
    out = plan.model_copy(deep=True)
    out.aspect = aspect
    wide_out = ASPECT_SIZE[aspect][0] > ASPECT_SIZE[aspect][1]
    for c in out.clips:
        m = media[c.media_id]
        wide_in = m["width"] >= m["height"]
        if c.fit in ("fill", "track") and wide_in != wide_out:
            has_face = (analysis.get(c.media_id) or {}).get("faces")
            c.fit = "track" if has_face else "blur_bg"
    return out


@app.post("/api/projects/{pid}/export")
def export_final(pid: str, body: ExportIn):
    project = load(pid)
    if not project["plan"]:
        raise HTTPException(400, "Generează întâi un montaj.")
    quality = body.quality if body.quality in render.QUALITY else "1080p"
    main_aspect = project["plan"]["aspect"]
    formats = [main_aspect] + [f for f in body.formats if f in ASPECT_SIZE and f != main_aspect]

    def work(step):
        project = load(pid)
        d = pdir(pid)
        plan = EditPlan.model_validate(project["plan"])
        media = media_map(project)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = re.sub(r"[^A-Za-z0-9-]+", "-", plan.title).strip("-")[:40] or "montaj"
        out = d / "exports" / f"{base}_{stamp}"
        out.mkdir(parents=True, exist_ok=True)
        share = 0.8 / len(formats)
        main_video = None
        for k, aspect in enumerate(formats):
            p = plan if aspect == main_aspect else reframe(plan, aspect, media, project["analysis"])
            suffix = "" if k == 0 else "_" + aspect.replace(":", "x")
            video = out / f"{base}{suffix}.mp4"
            lo = share * k
            render_plan(project, p, video, quality,
                        lambda pr=None, msg=None: step(pr, (msg or "Randez") + f" ({aspect}, {quality})"),
                        lo, lo + share)
            main_video = main_video or video
        step(0.82, "Export MP3 (doar sunetul)")
        render.export_mp3(main_video, out / f"{base}.mp3")
        step(0.85, "Copertă JPG + PNG")
        render.export_cover(plan, media, d / "media", d / "work", out / f"{base}_coperta", quality)
        step(0.88, "Fișiere pentru DaVinci Resolve / CapCut")
        (out / f"{base}.fcpxml").write_text(export.fcpxml(plan, media, d / "media"), encoding="utf-8")
        (out / f"{base}.edl").write_text(export.edl(plan, media), encoding="utf-8")
        (out / f"{base}.srt").write_text(export.srt(plan), encoding="utf-8")
        (out / f"{base}_plan.json").write_text(plan.model_dump_json(indent=1), encoding="utf-8")
        step(0.92, "Scriu textele pentru postare (descriere, hashtag-uri, hook-uri)")
        copy = None
        if api_key():
            try:
                frames = preview_frames(pid, 6) if load(pid).get("preview") else []
                copy = agent.social_copy(frames, plan, project["settings"], api_key(), load_settings()["model"])
            except Exception as exc:
                step(None, f"Textele AI nu au mers ({agent.describe_error(exc)}); folosesc un șablon")
        copy = copy or agent.template_copy(plan)
        (out / "postare.txt").write_text(export.post_text(copy), encoding="utf-8")
        files = sorted(f"exports/{out.name}/{f.name}" for f in out.iterdir())
        update(pid, lambda p: (p["exports"].insert(0, {"folder": out.name, "quality": quality, "formats": formats,
                                                       "time": time.time(), "files": files}),
                               p.__setitem__("social", copy.model_dump())))

    return start_job(pid, "export", work)


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    job = _jobs.get(jid)
    if not job:
        raise HTTPException(404, "Job inexistent")
    return job


# ----------------------------------------------------------------- files & UI

@app.get("/files/{pid}/{path:path}")
def project_file(pid: str, path: str, download: bool = False):
    d = pdir(pid).resolve()
    target = (d / path).resolve()
    if d not in target.parents or not target.is_file():
        raise HTTPException(404, "Fișier inexistent")
    return FileResponse(target, filename=target.name if download else None)


app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("MONTAJ_PORT", "8765"))
    if not ff.available():
        print("ATENȚIE: ffmpeg nu e instalat sau nu e în PATH. Aplicația pornește, dar nu poate randa.")
    if os.environ.get("MONTAJ_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
