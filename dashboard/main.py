"""
Web dashboard for editing YAML configs and triggering generate/build/deploy.

Run from repo root:

  uvicorn dashboard.main:app --reload --port 8765
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core import (
    ChuteConfig,
    CommandResult,
    ConfigManager,
    build_chute,
    chutes_list,
    chutes_logs,
    chutes_on_path,
    deploy_chute,
    get_template_names,
    module_ref,
    seed_builtin_templates,
    write_chute_module,
)
from core.deployer import iter_build_chute_stream, iter_deploy_chute_stream
from core.bittensor_wallet import resolve_bittensor_ss58
from core.chutes_api_client import (
    api_get_authenticated,
    api_get_public,
    api_post_change_bt_auth,
    api_request_authenticated,
    probe_chutes_api,
)
from core.credentials_store import (
    load_credentials,
    mask_api_key,
    parse_settings_form,
    save_credentials,
    write_minimal_chutes_ini,
)

app = FastAPI(title="Chutes", version="0.1.0")

app.mount(
    "/static",
    StaticFiles(directory=str(ROOT / "dashboard" / "static")),
    name="static",
)

templates = Jinja2Templates(directory=str(ROOT / "dashboard" / "templates"))

PWD_WINDOWS_HINT = (
    "The Chutes CLI does not run in Windows Python (missing Unix module 'pwd'). "
    "On a Windows-only PC, use WSL2: Ubuntu from the Microsoft Store / wsl --install, "
    "then install Python + chutes inside WSL and run build/deploy there (same machine). "
    "See README section “Windows only?”."
)


def cli_stderr_hint(stderr: str) -> Optional[str]:
    """Short explanation for common CLI failures (shown in API JSON and UI)."""
    if not stderr:
        return None
    s = stderr
    if "No module named 'pwd'" in s or 'No module named "pwd"' in s or "module 'pwd'" in s:
        return PWD_WINDOWS_HINT
    if "ModuleNotFoundError" in s and "pwd" in s:
        return PWD_WINDOWS_HINT
    return None


def manager() -> ConfigManager:
    return ConfigManager(str(ROOT / "configs"))


def _api_context() -> tuple[str, str]:
    c = load_credentials(ROOT)
    return c.effective_base_url(), c.api_key.strip()


@app.on_event("startup")
def _startup() -> None:
    tdir = ROOT / "configs" / "templates"
    if not any(tdir.glob("*.yaml")):
        seed_builtin_templates(ROOT)
    (ROOT / "chute_packages").mkdir(parents=True, exist_ok=True)
    (ROOT / "chute_packages" / "__init__.py").write_text(
        '"""Generated Chute modules."""\n', encoding="utf-8"
    )


@app.get("/settings/account", response_class=HTMLResponse)
async def settings_account(request: Request):
    creds = load_credentials(ROOT)
    ini_path = write_minimal_chutes_ini(ROOT, creds)
    return templates.TemplateResponse(
        request,
        "settings_account.html",
        {
            "creds": creds,
            "key_masked": mask_api_key(creds.api_key),
            "fingerprint_masked": mask_api_key(creds.account_fingerprint, keep=4),
            "generated_ini": str(ini_path.relative_to(ROOT)) if ini_path else "",
        },
    )


@app.post("/settings/account")
async def settings_account_save(
    api_key: str = Form(""),
    api_base_url: str = Form(""),
    chutes_config_path: str = Form(""),
    account_fingerprint: str = Form(""),
    clear_key: Optional[str] = Form(None),
    clear_fingerprint: Optional[str] = Form(None),
):
    existing = load_credentials(ROOT)
    new_creds = parse_settings_form(
        api_key=api_key,
        api_base_url=api_base_url,
        chutes_config_path=chutes_config_path,
        existing=existing,
        clear_key=bool(clear_key),
        account_fingerprint=account_fingerprint,
        clear_fingerprint=bool(clear_fingerprint),
    )
    save_credentials(ROOT, new_creds)
    write_minimal_chutes_ini(ROOT, new_creds)
    return RedirectResponse(url="/settings/account", status_code=303)


@app.post("/api/probe")
async def api_probe(
    api_key: str = Form(""),
    api_base_url: str = Form(""),
):
    """Test API key against Chutes HTTP API (see API reference)."""
    existing = load_credentials(ROOT)
    key = (api_key or "").strip() or existing.api_key
    base = (api_base_url or "").strip() or existing.api_base_url
    return probe_chutes_api(key, base)


@app.post("/api/account/link-bittensor")
async def api_account_link_bittensor(
    fingerprint: str = Form(""),
    coldkey: str = Form(""),
    hotkey: str = Form(""),
):
    """
    POST /users/change_bt_auth using the saved API key and fingerprint (website → local wallet).
    """
    creds = load_credentials(ROOT)
    key = creds.api_key.strip()
    fp = (fingerprint or "").strip() or creds.account_fingerprint.strip()
    if not fp:
        return {
            "ok": False,
            "error": "Fingerprint required: paste it under Account (Advanced) and Save, or send it in this request.",
        }
    if not key:
        return {"ok": False, "error": "Save an API key on the Account page first."}

    wr = Path.home() / ".bittensor" / "wallets"
    cold_ss58, hot_ss58, err = resolve_bittensor_ss58(
        wallets_root=wr,
        coldkey=(coldkey or "").strip(),
        hotkey=(hotkey or "").strip(),
    )
    if err:
        return {"ok": False, "error": err}

    r = api_post_change_bt_auth(
        creds.effective_base_url(),
        key,
        {"coldkey": cold_ss58, "hotkey": hot_ss58},
        fingerprint=fp,
        timeout=90.0,
    )
    out = {
        "ok": r.get("ok", False),
        "status": r.get("status"),
        "coldkey": cold_ss58,
        "hotkey": hot_ss58,
        "data": r.get("data"),
        "error": (r.get("error") or "")[:4000],
    }
    return out


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
    creds = load_credentials(ROOT)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "rows": rows,
            "root": "",
            "api_key_configured": bool(creds.api_key.strip()),
            "chutes_cli_on_path": chutes_on_path(),
        },
    )


@app.get("/api/health-summary")
async def api_health_summary():
    base, _ = _api_context()
    ping = api_get_public(base, "/ping")
    c = load_credentials(ROOT)
    return {
        "api_key_configured": bool(c.api_key.strip()),
        "chutes_on_path": chutes_on_path(),
        "api_base_url": c.effective_base_url(),
        "ping_ok": bool(ping.get("ok")),
        "ping_status": ping.get("status"),
    }


@app.get("/api/cli/logs")
async def api_cli_logs(
    chute_name: str = Query(..., min_length=1, description="Platform chute name for chutes logs"),
    tail: int = Query(50, ge=1, le=500),
):
    """Wraps `chutes chutes logs <name> --tail N`."""
    res = chutes_logs(chute_name.strip(), tail=tail, repo_root=ROOT)
    return {
        "ok": res.ok,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "chute_name": chute_name.strip(),
    }


@app.get("/config/new", response_class=HTMLResponse)
async def config_new_form(request: Request, template: str = "music"):
    names = get_template_names()
    if template not in names:
        template = names[0]
    return templates.TemplateResponse(
        request,
        "config_new.html",
        {"templates": names, "selected": template},
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
    return RedirectResponse(url=f"/chute/{name}", status_code=303)


@app.get("/config/{name}/edit", response_class=HTMLResponse)
async def config_edit(request: Request, name: str):
    m = manager()
    path = m.get_config_path(name)
    if not path.exists():
        raise HTTPException(404, "config not found")
    raw = path.read_text(encoding="utf-8")
    return templates.TemplateResponse(
        request,
        "config_edit.html",
        {"name": name, "yaml_text": raw},
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


@app.get("/chute/{name}", response_class=HTMLResponse)
async def chute_flow_page(request: Request, name: str):
    """Simple step-by-step deploy flow for one local chute."""
    m = manager()
    if not m.config_exists(name):
        raise HTTPException(404, "Chute not found")
    chute_type = ""
    username = ""
    model_name = ""
    load_error: Optional[str] = None
    try:
        cfg = m.load_config(name)
        chute_type = cfg.chute_type
        username = cfg.username
        model_name = cfg.model.name
    except Exception as exc:
        load_error = str(exc)
    creds = load_credentials(ROOT)
    return templates.TemplateResponse(
        request,
        "chute_flow.html",
        {
            "name": name,
            "chute_type": chute_type,
            "username": username,
            "model_name": model_name,
            "load_error": load_error,
            "api_key_configured": bool(creds.api_key.strip()),
            "chutes_cli_on_path": chutes_on_path(),
            # Chutes PyPI CLI imports Unix-only stdlib (e.g. pwd) — often breaks on native Windows.
            "is_windows": sys.platform == "win32",
        },
    )


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
    res = build_chute(ref, cwd=cwd, wait=True, repo_root=ROOT)
    out: dict = {
        "ok": res.ok,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "ref": ref,
    }
    hint = cli_stderr_hint(res.stderr or "")
    if hint:
        out["hint"] = hint
    return out


@app.post("/api/build/{name}/stream")
async def api_build_stream(name: str):
    """Stream ``chutes build`` stdout/stderr as NDJSON (``application/x-ndjson``)."""
    m = manager()

    def error_stream(msg: str):
        yield json.dumps({"type": "log", "message": msg}) + "\n"
        yield json.dumps(
            {
                "type": "result",
                "ok": False,
                "returncode": -1,
                "stdout": "",
                "stderr": msg,
                "ref": "",
            }
        ) + "\n"

    try:
        cfg = m.load_config(name)
    except Exception as e:
        return StreamingResponse(error_stream(str(e)), media_type="application/x-ndjson")

    ref = module_ref(cfg)
    cwd = ROOT / "chute_packages"
    return StreamingResponse(
        iter_build_chute_stream(ref, cwd=cwd, repo_root=ROOT),
        media_type="application/x-ndjson",
    )


@app.post("/api/deploy/{name}/stream")
async def api_deploy_stream(name: str):
    """Stream ``chutes deploy`` stdout/stderr as NDJSON."""
    m = manager()

    def error_stream(msg: str):
        yield json.dumps({"type": "log", "message": msg}) + "\n"
        yield json.dumps(
            {
                "type": "result",
                "ok": False,
                "returncode": -1,
                "stdout": "",
                "stderr": msg,
                "ref": "",
            }
        ) + "\n"

    try:
        cfg = m.load_config(name)
    except Exception as e:
        return StreamingResponse(error_stream(str(e)), media_type="application/x-ndjson")

    ref = module_ref(cfg)
    cwd = ROOT / "chute_packages"
    return StreamingResponse(
        iter_deploy_chute_stream(ref, cwd=cwd, repo_root=ROOT),
        media_type="application/x-ndjson",
    )


@app.post("/api/deploy/{name}")
async def api_deploy(name: str):
    m = manager()
    cfg = m.load_config(name)
    ref = module_ref(cfg)
    cwd = ROOT / "chute_packages"
    res = deploy_chute(ref, cwd=cwd, accept_fee=True, repo_root=ROOT)
    out: dict = {
        "ok": res.ok,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "ref": ref,
    }
    hint = cli_stderr_hint(res.stderr or "")
    if hint:
        out["hint"] = hint
    return out


@app.get("/diagnostics", response_class=HTMLResponse)
async def diagnostics_page(request: Request):
    """Plain-language troubleshooting page (replaces raw JSON for most users)."""
    creds = load_credentials(ROOT)
    try:
        res = chutes_list(repo_root=ROOT)
    except Exception as e:
        res = CommandResult(ok=False, returncode=-1, stdout="", stderr=str(e))
    return templates.TemplateResponse(
        request,
        "diagnostics.html",
        {
            "api_key_configured": bool(creds.api_key.strip()),
            "chutes_on_path": chutes_on_path(),
            "api_base_url": creds.effective_base_url(),
            "chutes_config_path_set": bool(creds.chutes_config_path.strip()),
            "returncode": res.returncode,
            "list_ok": res.ok,
            "stdout": res.stdout or "",
            "stderr": res.stderr or "",
        },
    )


@app.get("/api/status")
async def api_status():
    c = load_credentials(ROOT)
    try:
        res = chutes_list(repo_root=ROOT)
    except Exception as e:
        return {
            "chutes_on_path": chutes_on_path(),
            "api_key_configured": bool(c.api_key.strip()),
            "api_base_url": c.effective_base_url(),
            "chutes_config_path_set": bool(c.chutes_config_path.strip()),
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"chutes_list failed: {e}",
        }
    return {
        "chutes_on_path": chutes_on_path(),
        "api_key_configured": bool(c.api_key.strip()),
        "api_base_url": c.effective_base_url(),
        "chutes_config_path_set": bool(c.chutes_config_path.strip()),
        "ok": res.ok,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
    }


# --- Chutes REST API browser (https://chutes.ai/docs/api-reference/overview) ---


@app.get("/platform")
async def platform_redirect():
    """Old URL → advanced tools (bookmarks still work)."""
    return RedirectResponse(url="/platform/advanced", status_code=302)


@app.get("/platform/advanced", response_class=HTMLResponse)
async def platform_advanced_page(request: Request):
    base, key = _api_context()
    return templates.TemplateResponse(
        request,
        "platform.html",
        {
            "api_base_url": base,
            "has_api_key": bool(key),
        },
    )


@app.get("/api/platform/ping")
async def platform_ping():
    base, _ = _api_context()
    return api_get_public(base, "/ping")


@app.get("/api/platform/pricing")
async def platform_pricing():
    base, _ = _api_context()
    return api_get_public(base, "/pricing")


@app.get("/api/platform/chutes")
async def platform_list_chutes(
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(0, ge=0),
    name: str = Query(""),
):
    base, key = _api_context()
    q: dict = {"limit": limit, "page": page}
    if name.strip():
        q["name"] = name.strip()
    return api_get_authenticated(base, "/chutes/", key, query=q)


@app.get("/api/platform/images")
async def platform_list_images(
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(0, ge=0),
    name: str = Query(""),
    tag: str = Query(""),
):
    base, key = _api_context()
    q: dict = {"limit": limit, "page": page}
    if name.strip():
        q["name"] = name.strip()
    if tag.strip():
        q["tag"] = tag.strip()
    return api_get_authenticated(base, "/images/", key, query=q)


@app.get("/api/platform/chutes/detail/{chute_id:path}")
async def platform_chute_detail(chute_id: str):
    base, key = _api_context()
    enc = quote(chute_id.strip(), safe="")
    return api_get_authenticated(base, f"/chutes/{enc}", key)


@app.get("/api/platform/chutes/warmup/{chute_id:path}")
async def platform_chute_warmup(chute_id: str):
    """GET /chutes/warmup/{chute_id_or_name} — see Chutes API reference."""
    base, key = _api_context()
    enc = quote(chute_id.strip(), safe="")
    return api_get_authenticated(base, f"/chutes/warmup/{enc}", key)


@app.get("/api/platform/me/quotas")
async def platform_me_quotas():
    """GET /users/me/quotas — requires auth."""
    base, key = _api_context()
    return api_get_authenticated(base, "/users/me/quotas", key)


@app.get("/api/platform/me/discounts")
async def platform_me_discounts():
    base, key = _api_context()
    return api_get_authenticated(base, "/users/me/discounts", key)


@app.post("/api/platform/chutes/share")
async def platform_share_chute(
    chute_id_or_name: str = Form(...),
    user_id_or_name: str = Form(...),
):
    """POST /chutes/share — see Chutes API reference."""
    base, key = _api_context()
    body = {
        "chute_id_or_name": chute_id_or_name.strip(),
        "user_id_or_name": user_id_or_name.strip(),
    }
    return api_request_authenticated(
        "POST", base, "/chutes/share", key, json_body=body, timeout=60.0
    )


@app.delete("/api/platform/chutes/by-id/{chute_id:path}")
async def platform_delete_chute(
    chute_id: str,
    confirm: str = Query(..., description="Must exactly match chute id/name in path"),
):
    """DELETE /chutes/{chute_id} — confirm must match path (typed confirm)."""
    raw = chute_id.strip()
    if confirm.strip() != raw:
        raise HTTPException(
            status_code=400,
            detail="Query param 'confirm' must exactly match the chute id/name in the URL.",
        )
    base, key = _api_context()
    enc = quote(raw, safe="")
    return api_request_authenticated(
        "DELETE", base, f"/chutes/{enc}", key, timeout=120.0
    )


@app.get("/api/platform/images/{image_id}/logs")
async def platform_image_logs(
    image_id: str,
    offset: str = Query("", description="Optional log offset cursor"),
):
    """GET /images/{image_id}/logs — build logs."""
    base, key = _api_context()
    enc = quote(image_id.strip(), safe="")
    q: dict = {}
    if offset.strip():
        q["offset"] = offset.strip()
    return api_get_authenticated(
        base, f"/images/{enc}/logs", key, query=q or None, timeout=120.0
    )
