"""
Web dashboard for editing YAML configs and triggering generate/build/deploy.

Run from repo root:

  uvicorn dashboard.main:app --reload --port 8765
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml
from urllib.parse import quote

from fastapi import Body, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
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
    get_template_catalog,
    get_template_names,
    group_local_configs_for_home,
    module_ref,
    seed_builtin_templates,
    uses_chutes_platform_image,
    write_chute_module,
)
from core.deployer import iter_build_chute_stream, iter_deploy_chute_stream
from core.playground_catalog import group_catalog, normalize_row, pick_chute_rows
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
from core.openapi_playground import extract_fields_for_operation, list_json_body_operations
from core.chutes_playground_proxy import fetch_chute_openapi, proxy_chute_call
from core.chutes_public_image import get_playground_meta, proxy_image_generate

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


CUSTOM_IMAGE_BALANCE_HINT = (
    "Chutes requires an account balance of at least $50 to build custom Docker images "
    "(any chute that defines Image(...) with from_base/run_command). "
    "Pre-built templates (vLLM, SGLang, etc.) use platform images and do not need that build step — "
    "see https://chutes.ai/docs/guides/templates — but they are for LLM inference, not stacks like MusicGen."
)


def cli_stderr_hint(stderr: str, stdout: str = "") -> Optional[str]:
    """Short explanation for common CLI failures (shown in API JSON and UI)."""
    s = f"{stderr or ''}\n{stdout or ''}"
    if not s.strip():
        return None
    if "balance of >= $50" in s or "minimum balance of $50" in s.lower():
        return CUSTOM_IMAGE_BALANCE_HINT
    if "no need to build anything" in s.lower() or "pre-defined/standard image" in s.lower():
        return (
            "This chute uses a Chutes pre-built template image — skip `chutes build` and run "
            "`chutes deploy … --accept-fee` after Prepare, or use the hosted API on image.chutes.ai "
            "for public models (see Deploy page)."
        )
    if "No module named 'pwd'" in s or 'No module named "pwd"' in s or "module 'pwd'" in s:
        return PWD_WINDOWS_HINT
    if "ModuleNotFoundError" in s and "pwd" in s:
        return PWD_WINDOWS_HINT
    return None


def manager() -> ConfigManager:
    return ConfigManager(str(ROOT / "configs"))


def _iter_skip_platform_build_stream(ref: str) -> Iterator[str]:
    """NDJSON stream when ``chutes build`` is not used (standard template image)."""
    msg = (
        "Skipping image build: this chute uses a Chutes pre-built template image "
        "(the CLI reports “no need to build”). Use Publish (deploy) next."
    )
    yield json.dumps({"type": "log", "message": msg}) + "\n"
    yield json.dumps(
        {
            "type": "result",
            "ok": True,
            "returncode": 0,
            "stdout": msg,
            "stderr": "",
            "ref": ref,
            "skipped": True,
        }
    ) + "\n"


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


@app.get("/playground", response_class=HTMLResponse)
async def playground_hub_page(request: Request):
    """Hub showing ready-to-use chutes from the catalog, grouped by template."""
    creds = load_credentials(ROOT)
    return templates.TemplateResponse(
        request,
        "playground_hub.html",
        {"api_key_configured": bool(creds.api_key.strip())},
    )


@app.get("/playground/chute", response_class=HTMLResponse)
async def playground_chute_page(request: Request, url: str = ""):
    """Dynamic generation page for a single deployed chute (prefilled from hub)."""
    creds = load_credentials(ROOT)
    chute_url = (url or "").strip()
    return templates.TemplateResponse(
        request,
        "playground_chute.html",
        {
            "api_key_configured": bool(creds.api_key.strip()),
            "chute_url": chute_url,
        },
    )


@app.get("/playground/image", response_class=HTMLResponse)
async def playground_image_page(request: Request):
    """Public image API: dynamic form + proxy to image.chutes.ai (API key on server only)."""
    creds = load_credentials(ROOT)
    return templates.TemplateResponse(
        request,
        "playground_image.html",
        {
            "api_key_configured": bool(creds.api_key.strip()),
        },
    )


@app.get("/api/playground/image/meta")
async def api_playground_image_meta():
    """OpenAPI-derived fields (with fallback) for dynamic form."""
    return get_playground_meta()


@app.post("/api/playground/image/run")
async def api_playground_image_run(body: Dict[str, Any] = Body(...)):
    """Proxy POST /generate to image.chutes.ai."""
    creds = load_credentials(ROOT)
    key = creds.api_key.strip()
    if not key:
        return JSONResponse(
            {"ok": False, "error": "Save your Chutes API key under Account first."},
            status_code=401,
        )
    ok, result = proxy_image_generate(key, body)
    if ok:
        return {"ok": True, **result}
    status = result.get("status")
    code = status if isinstance(status, int) and 400 <= status < 600 else 502
    return JSONResponse({"ok": False, **result}, status_code=code)


@app.get("/api/playground/catalog")
async def api_playground_catalog(
    limit: int = Query(100, ge=1, le=100),
    page: int = Query(0, ge=0),
    chute_type: str = Query(
        "",
        description="Filter by type: llm, image_generation, video, tts, speech_to_text, music_generation, embeddings.",
    ),
):
    """
    Chutes list with include_public=true, grouped by standard_template for the playground hub.
    """
    base, key = _api_context()
    if not key:
        return JSONResponse(
            {"ok": False, "error": "Save your Chutes API key under Account first."},
            status_code=401,
        )
    q: dict = {"limit": limit, "page": page, "include_public": True}
    if chute_type.strip():
        q["template"] = chute_type.strip()
    r = api_get_authenticated(base, "/chutes/", key, query=q)
    if not r.get("ok"):
        return JSONResponse(
            {"ok": False, "error": r.get("error"), "detail": r},
            status_code=502,
        )
    rows = pick_chute_rows(r.get("data"))
    if page == 0 and limit >= 100 and len(rows) >= 100:
        q2 = {"limit": limit, "page": 1, "include_public": True}
        if chute_type.strip():
            q2["template"] = chute_type.strip()
        r2 = api_get_authenticated(base, "/chutes/", key, query=q2)
        if r2.get("ok"):
            rows = rows + pick_chute_rows(r2.get("data"))
    normalized: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for row in rows:
        n = normalize_row(row)
        if not n:
            continue
        u = n["base_url"]
        if u in seen_urls:
            continue
        seen_urls.add(u)
        normalized.append(n)
    groups = group_catalog(normalized)
    return {
        "ok": True,
        "groups": groups,
        "total": len(normalized),
        "page": page,
        "limit": limit,
    }


@app.post("/api/playground/chute/call")
async def api_playground_chute_call(body: Dict[str, Any] = Body(...)):
    """
    Proxy a request to a deployed chute at https://*.chutes.ai (SSRF-restricted).
    Body: base_url, path, method (GET/POST/PUT/DELETE), json (optional object for POST/PUT).
    """
    creds = load_credentials(ROOT)
    key = creds.api_key.strip()
    if not key:
        return JSONResponse(
            {"ok": False, "error": "Save your Chutes API key under Account first."},
            status_code=401,
        )
    base = str(body.get("base_url") or "").strip()
    path = str(body.get("path") or "/")
    method = str(body.get("method") or "POST").strip()
    jb = body.get("json", {})
    if method.upper() in ("GET", "DELETE"):
        jb = None
    elif jb is not None and not isinstance(jb, (dict, list)):
        return JSONResponse(
            {"ok": False, "error": "Field 'json' must be a JSON object or array (or omitted)."},
            status_code=400,
        )
    ok, result = proxy_chute_call(key, base, path, method, json_body=jb)
    if ok:
        return {"ok": True, **result}
    status = result.get("status")
    code = status if isinstance(status, int) and 400 <= status < 600 else 502
    return JSONResponse({"ok": False, **result}, status_code=code)


@app.post("/api/playground/chute/openapi")
async def api_playground_chute_openapi(body: Dict[str, Any] = Body(...)):
    """Fetch openapi.json from a deployed chute (Bearer key); return JSON-body operations."""
    creds = load_credentials(ROOT)
    key = creds.api_key.strip()
    if not key:
        return JSONResponse(
            {"ok": False, "error": "Save your Chutes API key under Account first."},
            status_code=401,
        )
    base = str(body.get("base_url") or "").strip()
    openapi, err = fetch_chute_openapi(key, base)
    if err or not openapi:
        return JSONResponse(
            {"ok": False, "error": err or "Empty OpenAPI response"},
            status_code=502,
        )
    info = openapi.get("info") if isinstance(openapi.get("info"), dict) else {}
    return {
        "ok": True,
        "operations": list_json_body_operations(openapi),
        "title": (info.get("title") or "")[:200],
        "version": (info.get("version") or "")[:80],
    }


@app.post("/api/playground/chute/openapi-fields")
async def api_playground_chute_openapi_fields(body: Dict[str, Any] = Body(...)):
    """Resolve request body schema for one operation → same field shape as the image playground."""
    creds = load_credentials(ROOT)
    key = creds.api_key.strip()
    if not key:
        return JSONResponse(
            {"ok": False, "error": "Save your Chutes API key under Account first."},
            status_code=401,
        )
    base = str(body.get("base_url") or "").strip()
    path = str(body.get("path") or "")
    method = str(body.get("method") or "POST").strip()
    if not path.startswith("/"):
        path = "/" + path
    openapi, err = fetch_chute_openapi(key, base)
    if err or not openapi:
        return JSONResponse(
            {"ok": False, "error": err or "Could not load OpenAPI"},
            status_code=502,
        )
    fields = extract_fields_for_operation(openapi, path, method.lower())
    if not fields:
        return JSONResponse(
            {
                "ok": False,
                "error": "No application/json request body schema for this path/method.",
            },
            status_code=400,
        )
    model_presets = ["default"]
    for f in fields:
        if f.get("key") == "model":
            en = f.get("enum")
            if isinstance(en, list) and len(en) > 0:
                model_presets = [str(x) for x in en]
            break
    return {"ok": True, "fields": fields, "model_presets": model_presets}


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
            uses_platform = uses_chutes_platform_image(c.chute_type)
            playground_url = "/playground/image"
            if c.chute_type == "diffusion":
                playground_url = "/playground/image?model=" + quote(c.model.name, safe="")
            rows.append(
                {
                    "name": n,
                    "type": c.chute_type,
                    "username": c.username,
                    "model": c.model.name,
                    "uses_platform_image": uses_platform,
                    "playground_url": playground_url,
                }
            )
        except Exception as exc:
            rows.append({"name": n, "error": str(exc)})
    creds = load_credentials(ROOT)
    catalog = get_template_catalog()
    new_chute_links = [
        {"href": f"/config/new#tg-{g['id']}", "label": g["label"]}
        for g in catalog
        if any(o.get("stack") == "platform" for o in g["options"])
    ]
    new_chute_links.append({"href": "/config/new", "label": "All templates"})
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "rows": rows,
            "home_sections": group_local_configs_for_home(rows),
            "new_chute_links": new_chute_links,
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
        template = "music" if "music" in names else names[0]
    catalog = get_template_catalog()
    return templates.TemplateResponse(
        request,
        "config_new.html",
        {"template_groups": catalog, "selected": template},
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
    skip_build = False
    public_image_curl_example = ""
    try:
        cfg = m.load_config(name)
        chute_type = cfg.chute_type
        username = cfg.username
        model_name = cfg.model.name
        skip_build = uses_chutes_platform_image(chute_type)
        if chute_type == "diffusion" and model_name:
            payload = {
                "model": model_name,
                "prompt": "A beautiful sunset over mountains",
                "negative_prompt": "blur, distortion, low quality",
                "guidance_scale": 7.5,
                "width": 1024,
                "height": 1024,
                "num_inference_steps": 50,
            }
            public_image_curl_example = (
                "curl -X POST 'https://image.chutes.ai/generate' \\\n"
                '  -H "Authorization: Bearer $CHUTES_API_TOKEN" \\\n'
                '  -H "Content-Type: application/json" \\\n'
                f"  -d '{json.dumps(payload)}'"
            )
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
            "skip_build": skip_build,
            "public_image_curl_example": public_image_curl_example,
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
    if uses_chutes_platform_image(cfg.chute_type):
        msg = (
            "Skipping build: Chutes pre-built template image — run deploy only "
            "(no custom Docker image to build)."
        )
        return {
            "ok": True,
            "returncode": 0,
            "stdout": msg,
            "stderr": "",
            "ref": ref,
            "skipped": True,
        }
    cwd = ROOT / "chute_packages"
    res = build_chute(ref, cwd=cwd, wait=True, repo_root=ROOT)
    out: dict = {
        "ok": res.ok,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "ref": ref,
    }
    hint = cli_stderr_hint(res.stderr or "", res.stdout or "")
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
    if uses_chutes_platform_image(cfg.chute_type):
        return StreamingResponse(
            _iter_skip_platform_build_stream(ref),
            media_type="application/x-ndjson",
        )
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
    hint = cli_stderr_hint(res.stderr or "", res.stdout or "")
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
    include_public: bool = Query(
        False,
        description="When true, asks Chutes to include public chutes (marketplace-style catalog).",
    ),
    template: str = Query(
        "",
        description="Optional filter by standard template type (Chutes API query param).",
    ),
    chute_type: str = Query(
        "",
        description="Filter by chute type (image_generation, llm, tts, etc.).",
    ),
):
    base, key = _api_context()
    q: dict = {"limit": limit, "page": page}
    if name.strip():
        q["name"] = name.strip()
    if include_public:
        q["include_public"] = True
    template_val = template.strip() or chute_type.strip()
    if template_val:
        q["template"] = template_val
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
