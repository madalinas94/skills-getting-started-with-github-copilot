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
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import agent, analyze, autoplan, export, ff, presets, render, validate
from engine.plan import EditPlan, timeline

ROOT = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("MONTAJ_WORKSPACE", ROOT / "workspace"))
PROJECTS = WORKSPACE / "projects"
SETTINGS_FILE = WORKSPACE / "settings.json"
FRAMES_PER_VIDEO = 5
PROJECTS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Montaj")
_lock = threading.RLock()
_jobs: dict = {}


# ----------------------------------------------------------------- storage

def load_settings() -> dict:
    data = {"api_key": "", "model": agent.DEFAULT_MODEL, "effort": "medium"}
    if SETTINGS_FILE.exists():
        data.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    return data


def api_key() -> str | None:
    return load_settings().get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or None


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


def new_project(name: str) -> dict:
    pid = uuid.uuid4().hex[:12]
    d = PROJECTS / pid
    for sub in ("media", "frames", "thumbs", "work", "exports"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    project = {
        "id": pid, "name": name or "Proiect nou", "created": time.time(),
        "media": [], "analysis": {}, "plan": None, "issues": [], "history": [], "chat": [],
        "settings": {"preset": presets.DEFAULT, "aspect": "", "duration": 30, "rules": "",
                     "title": "", "outro": "", "captions": False, "auto_color": True},
        "preview": None, "exports": [],
    }
    save(project)
    return project


def media_map(project: dict, roles=("material", "music")) -> dict:
    return {m["id"]: m for m in project["media"] if m["role"] in roles}


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


def ensure_analysis(pid: str, step, lo=0.0, hi=0.3):
    project = load(pid)
    d = pdir(pid)
    todo = [m for m in project["media"] if m["id"] not in project["analysis"]]
    for i, m in enumerate(todo):
        step(lo + (hi - lo) * i / max(1, len(todo)), f"Analizez {m['name']} (cadre, scene, lumină, ritm)")
        info = analyze.analyze(m, d / "media" / m["file"], d / "frames", FRAMES_PER_VIDEO)
        if m["role"] == "example":
            info["style"] = analyze.style_fingerprint(m, info)
        update(pid, lambda p: p["analysis"].__setitem__(m["id"], info))
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


def render_preview(pid: str, step, lo: float):
    project = load(pid)
    d = pdir(pid)
    plan = EditPlan.model_validate(project["plan"])
    name = f"preview_{int(time.time())}.mp4"
    info = render.render(plan, media_map(project), d / "media", d / "work", d / "work" / name, "preview",
                         lambda p, msg="": step(lo + (1 - lo) * p, msg or None))

    def fn(p):
        old = p.get("preview")
        p["preview"] = {"file": f"work/{name}", **info, "time": time.time()}
        if old and old.get("file") and old["file"] != p["preview"]["file"]:
            (d / old["file"]).unlink(missing_ok=True)
    update(pid, fn)


# ----------------------------------------------------------------- API: app

@app.get("/api/status")
def status():
    s = load_settings()
    return {
        "ffmpeg": ff.available(),
        "has_key": bool(api_key()),
        "key_from_env": bool(os.environ.get("ANTHROPIC_API_KEY")) and not s.get("api_key"),
        "model": s["model"], "effort": s["effort"],
        "models": agent.MODELS,
        "presets": {k: {"label": v["label"], "aspect": v["aspect"], "duration": v["duration"],
                        "brief": v["brief"]} for k, v in presets.PRESETS.items()},
    }


class SettingsIn(BaseModel):
    api_key: str | None = None
    model: str | None = None
    effort: str | None = None


@app.post("/api/settings")
def save_settings(body: SettingsIn):
    s = load_settings()
    if body.api_key is not None:
        s["api_key"] = body.api_key.strip()
    if body.model in agent.MODELS:
        s["model"] = body.model
    if body.effort in ("low", "medium", "high", "xhigh", "max"):
        s["effort"] = body.effort
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
    project["running"] = next((j for j in _jobs.values()
                               if j["project"] == pid and j["status"] == "running"), None)
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
    return {"project": get_project(pid), "errors": errors}


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
    aspect: str = ""
    duration: float = 30
    rules: str = ""
    title: str = ""
    outro: str = ""
    captions: bool = False
    auto_color: bool = True


@app.put("/api/projects/{pid}/settings")
def put_settings(pid: str, body: ProjectSettings):
    update(pid, lambda p: p.__setitem__("settings", body.model_dump()))
    return {"ok": True}


# ----------------------------------------------------------------- API: the agent

class GenerateIn(BaseModel):
    mode: str = "ai"  # "ai" or "auto"


@app.post("/api/projects/{pid}/generate")
def generate(pid: str, body: GenerateIn):
    project = load(pid)
    if not any(m["role"] == "material" and m["kind"] in ("video", "image") for m in project["media"]):
        raise HTTPException(400, "Încarcă cel puțin un video sau o poză.")
    use_ai = body.mode == "ai"
    if use_ai and not api_key():
        raise HTTPException(400, "Lipsește cheia API Anthropic. Adaug-o în Setări sau folosește modul automat.")

    def work(step):
        project = ensure_analysis(pid, step, 0.0, 0.3)
        d = pdir(pid)
        settings = project["settings"]
        material = [m for m in project["media"] if m["role"] in ("material", "music")]
        visible = [m for m in project["media"] if m["role"] in ("material", "music", "example")]
        if use_ai:
            s = load_settings()
            step(0.32, f"Agentul AI se uită la cadre și scrie planul ({agent.MODELS.get(s['model'], s['model'])})")
            plan = agent.plan_edit(visible, project["analysis"], d / "frames", settings, api_key(),
                                   s["model"], s["effort"])
        else:
            step(0.32, "Construiesc planul automat (fără AI)")
            plan = autoplan.build(material, project["analysis"], settings)
        step(0.45, "Validez planul pe fișierele reale")
        plan, issues = validate.validate(plan, media_map(project), project["analysis"])
        if not plan.clips:
            raise RuntimeError("Planul nu are clipuri valide. " + " ".join(issues))
        set_plan(pid, plan, issues, "AI" if use_ai else "Automat")
        update(pid, lambda p: p["chat"].append({"role": "agent", "text": plan.summary, "time": time.time()}))
        render_preview(pid, step, 0.5)

    return start_job(pid, "generate", work)


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
                                 s["model"], s["effort"])
        plan, issues = validate.validate(plan, media_map(project), project["analysis"])
        set_plan(pid, plan, issues, "Revizie: " + feedback[:40])
        update(pid, lambda p: p["chat"].append({"role": "agent", "text": plan.summary, "time": time.time()}))
        render_preview(pid, step, 0.4)

    return start_job(pid, "revise", work)


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


class ExportIn(BaseModel):
    quality: str = "1080p"


@app.post("/api/projects/{pid}/export")
def export_final(pid: str, body: ExportIn):
    project = load(pid)
    if not project["plan"]:
        raise HTTPException(400, "Generează întâi un montaj.")
    quality = body.quality if body.quality in render.QUALITY else "1080p"

    def work(step):
        project = load(pid)
        d = pdir(pid)
        plan = EditPlan.model_validate(project["plan"])
        media = media_map(project)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = re.sub(r"[^A-Za-z0-9-]+", "-", plan.title).strip("-")[:40] or "montaj"
        out = d / "exports" / f"{base}_{stamp}"
        out.mkdir(parents=True, exist_ok=True)
        video = out / f"{base}.mp4"
        render.render(plan, media, d / "media", d / "work", video, quality,
                      lambda p, msg="": step(0.85 * p, (msg or "Randez") + f" ({quality})"))
        step(0.87, "Export MP3 (doar sunetul)")
        render.export_mp3(video, out / f"{base}.mp3")
        step(0.9, "Copertă JPG + PNG")
        render.export_cover(plan, media, d / "media", d / "work", out / f"{base}_coperta", quality)
        step(0.95, "Fișiere pentru DaVinci Resolve / CapCut")
        (out / f"{base}.fcpxml").write_text(export.fcpxml(plan, media, d / "media"), encoding="utf-8")
        (out / f"{base}.edl").write_text(export.edl(plan, media), encoding="utf-8")
        (out / f"{base}.srt").write_text(export.srt(plan), encoding="utf-8")
        (out / f"{base}_plan.json").write_text(plan.model_dump_json(indent=1), encoding="utf-8")
        files = sorted(f"exports/{out.name}/{f.name}" for f in out.iterdir())
        update(pid, lambda p: p["exports"].insert(0, {"folder": out.name, "quality": quality,
                                                      "time": time.time(), "files": files}))

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
