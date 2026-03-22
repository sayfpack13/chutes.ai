"""
Web dashboard for editing YAML configs and triggering generate/build/deploy.

Run from repo root:

  uvicorn dashboard.main:app --reload --port 8765
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core import (
    ChuteConfig,
    ConfigManager,
    build_chute,
    chutes_list,
    deploy_chute,
    get_template_names,
    module_ref,
    seed_builtin_templates,
    write_chute_module,
)

app = FastAPI(title="Chutes AI Manager", version="0.1.0")

app.mount(
    "/static",
    StaticFiles(directory=str(ROOT / "dashboard" / "static")),
    name="static",
)

templates = Jinja2Templates(directory=str(ROOT / "dashboard" / "templates"))


def manager() -> ConfigManager:
    return ConfigManager(str(ROOT / "configs"))


@app.on_event("startup")
def _startup() -> None:
    tdir = ROOT / "configs" / "templates"
    if not any(tdir.glob("*.yaml")):
        seed_builtin_templates(ROOT)
    (ROOT / "chute_packages").mkdir(parents=True, exist_ok=True)
    (ROOT / "chute_packages" / "__init__.py").write_text(
        '"""Generated Chute modules."""\n', encoding="utf-8"
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    m = manager()
    cfg_names = m.list_configs()
    rows = []
    for n in cfg_names:
        try:
            c = m.load_config(n)
            rows.append(
                {
                    "name": n,
                    "type": c.chute_type,
                    "username": c.username,
                    "model": c.model.name,
                }
            )
        except Exception as exc:
            rows.append({"name": n, "error": str(exc)})
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "rows": rows, "root": ""},
    )


@app.get("/config/new", response_class=HTMLResponse)
async def config_new_form(request: Request, template: str = "music"):
    names = get_template_names()
    if template not in names:
        template = names[0]
    return templates.TemplateResponse(
        "config_new.html",
        {"request": request, "templates": names, "selected": template},
    )


@app.post("/config/new")
async def config_new_create(
    request: Request,
    name: str = Form(...),
    template: str = Form(...),
    username: str = Form(""),
):
    from core.templates import get_template

    m = manager()
    name = name.strip().lower().replace(" ", "-")
    if not name:
        raise HTTPException(400, "name required")
    if m.config_exists(name):
        raise HTTPException(400, f"config {name} already exists")
    try:
        data = get_template(template)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    data["name"] = name
    if username.strip():
        data["username"] = username.strip()
    cfg = ChuteConfig(**data)
    m.save_config(cfg)
    return RedirectResponse(url=f"/config/{name}/edit", status_code=303)


@app.get("/config/{name}/edit", response_class=HTMLResponse)
async def config_edit(request: Request, name: str):
    m = manager()
    path = m.get_config_path(name)
    if not path.exists():
        raise HTTPException(404, "config not found")
    raw = path.read_text(encoding="utf-8")
    return templates.TemplateResponse(
        "config_edit.html",
        {"request": request, "name": name, "yaml_text": raw},
    )


@app.post("/config/{name}/edit")
async def config_save(request: Request, name: str, yaml_text: str = Form(...)):
    m = manager()
    try:
        data = yaml.safe_load(yaml_text) or {}
        cfg = ChuteConfig(**data)
        if cfg.name != name:
            raise HTTPException(400, "YAML name field must match URL name")
        m.save_config(cfg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Invalid YAML/config: {e}") from e
    return RedirectResponse(url=f"/config/{name}/edit", status_code=303)


@app.post("/config/{name}/delete")
async def config_delete(name: str):
    m = manager()
    if not m.delete_config(name):
        raise HTTPException(404, "config not found")
    return RedirectResponse(url="/", status_code=303)


@app.post("/api/generate/{name}")
async def api_generate(name: str):
    m = manager()
    cfg = m.load_config(name)
    path = write_chute_module(cfg, ROOT)
    return {"ok": True, "path": str(path.relative_to(ROOT)), "ref": module_ref(cfg)}


@app.post("/api/build/{name}")
async def api_build(name: str):
    m = manager()
    cfg = m.load_config(name)
    ref = module_ref(cfg)
    cwd = ROOT / "chute_packages"
    res = build_chute(ref, cwd=cwd, wait=True)
    return {
        "ok": res.ok,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "ref": ref,
    }


@app.post("/api/deploy/{name}")
async def api_deploy(name: str):
    m = manager()
    cfg = m.load_config(name)
    ref = module_ref(cfg)
    cwd = ROOT / "chute_packages"
    res = deploy_chute(ref, cwd=cwd, accept_fee=True)
    return {
        "ok": res.ok,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "ref": ref,
    }


@app.get("/api/status")
async def api_status():
    res = chutes_list()
    return {
        "ok": res.ok,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
    }
