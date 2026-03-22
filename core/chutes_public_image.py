"""
Chutes public image API (image.chutes.ai) — OpenAPI fetch + server-side proxy.

The dashboard never sends your API key to the browser; requests go server → Chutes.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from core.openapi_playground import extract_image_generate_fields

IMAGE_API_BASE = "https://image.chutes.ai"
OPENAPI_URL = f"{IMAGE_API_BASE}/openapi.json"

DEFAULT_MODEL_PRESETS: List[str] = [
    "stabilityai/stable-diffusion-xl-base-1.0",
]

DEFAULT_GENERATE_FIELDS: List[Dict[str, Any]] = [
    {
        "key": "model",
        "title": "Model (Hugging Face id)",
        "type": "string",
        "required": True,
        "default": "stabilityai/stable-diffusion-xl-base-1.0",
        "description": "Must be a model deployed on Chutes for this API. Other ids often return 404.",
        "widget": "model_select",
    },
    {
        "key": "prompt",
        "title": "Prompt",
        "type": "string",
        "required": True,
        "default": "",
        "description": "What to generate.",
        "widget": "textarea",
    },
    {
        "key": "negative_prompt",
        "title": "Negative prompt",
        "type": "string",
        "required": False,
        "default": "blur, distortion, low quality",
        "widget": "textarea",
    },
    {
        "key": "guidance_scale",
        "title": "Guidance scale",
        "type": "number",
        "required": False,
        "default": 7.5,
        "minimum": 1.0,
        "maximum": 20.0,
        "step": 0.5,
    },
    {
        "key": "width",
        "title": "Width",
        "type": "integer",
        "required": False,
        "default": 1024,
        "minimum": 128,
        "maximum": 2048,
        "step": 8,
    },
    {
        "key": "height",
        "title": "Height",
        "type": "integer",
        "required": False,
        "default": 1024,
        "minimum": 128,
        "maximum": 2048,
        "step": 8,
    },
    {
        "key": "num_inference_steps",
        "title": "Inference steps",
        "type": "integer",
        "required": False,
        "default": 50,
        "minimum": 1,
        "maximum": 150,
    },
    {
        "key": "seed",
        "title": "Seed (optional)",
        "type": "integer",
        "required": False,
        "default": None,
        "nullable": True,
    },
]

_openapi_cache: Optional[Dict[str, Any]] = None
_openapi_cache_ts: float = 0.0
_OPENAPI_TTL_SEC = 300.0


def _http_get_json(url: str, timeout: float = 20.0) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")[:2000]
        except OSError:
            body = ""
        return None, f"HTTP {e.code}: {body or e.reason}"
    except Exception as exc:
        return None, str(exc)


def get_openapi_cached() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    global _openapi_cache, _openapi_cache_ts
    now = time.monotonic()
    if _openapi_cache is not None and (now - _openapi_cache_ts) < _OPENAPI_TTL_SEC:
        return _openapi_cache, None
    data, err = _http_get_json(OPENAPI_URL)
    if err or not data:
        return None, err
    _openapi_cache = data
    _openapi_cache_ts = now
    return data, None


def get_playground_meta() -> Dict[str, Any]:
    openapi, err = get_openapi_cached()
    fields: Optional[List[Dict[str, Any]]] = None
    if openapi:
        fields = extract_image_generate_fields(openapi)
    if not fields:
        fields = [dict(f) for f in DEFAULT_GENERATE_FIELDS]

    model_presets: List[str] = list(DEFAULT_MODEL_PRESETS)
    for f in fields:
        if f.get("key") == "model":
            en = f.get("enum")
            if isinstance(en, list) and len(en) > 0:
                model_presets = [str(x) for x in en]
            break

    return {
        "image_api_base": IMAGE_API_BASE,
        "openapi_url": OPENAPI_URL,
        "openapi_ok": bool(openapi),
        "openapi_error": err if not openapi else None,
        "fields": fields,
        "model_presets": model_presets,
        "model_presets_note": (
            "The hosted API only accepts models that service runs. "
            "Presets follow OpenAPI when it lists an enum; otherwise a known-good default. "
            "Other model ids typically return 404."
        ),
    }


def proxy_image_generate(api_key: str, payload: Dict[str, Any], timeout: float = 300.0) -> Tuple[bool, Dict[str, Any]]:
    key = (api_key or "").strip()
    if not key:
        return False, {"error": "Save an API key under Account first."}
    url = f"{IMAGE_API_BASE}/generate"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "image/*, application/json, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if "application/json" in ct:
                try:
                    data = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    data = {"raw": raw.decode("utf-8", errors="replace")[:4000]}
                return True, {"content_type": "application/json", "json": data}
            b64 = base64.standard_b64encode(raw).decode("ascii")
            return True, {
                "content_type": ct or "application/octet-stream",
                "data_base64": b64,
                "size_bytes": len(raw),
            }
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:8000]
        except OSError:
            err_body = str(e)
        try:
            j = json.loads(err_body)
            return False, {"status": e.code, "error": j}
        except json.JSONDecodeError:
            return False, {"status": e.code, "error": err_body or e.reason}
    except Exception as exc:
        return False, {"error": str(exc)}
