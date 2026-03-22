"""
Proxy arbitrary HTTPS calls to deployed Chutes (*.chutes.ai) from the dashboard playground.

Restricts hosts to mitigate SSRF. API key is added server-side (never sent to the browser).
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse


def _host_ok(hostname: str) -> bool:
    h = (hostname or "").lower().strip(".")
    if not h or "." not in h:
        return False
    if h == "localhost" or h.endswith(".local"):
        return False
    return h.endswith(".chutes.ai")


def is_allowed_chutes_deploy_base(base_url: str) -> bool:
    try:
        p = urlparse((base_url or "").strip())
    except Exception:
        return False
    if p.scheme != "https":
        return False
    return _host_ok(p.hostname or "")


def fetch_chute_openapi(api_key: str, base_url: str, timeout: float = 30.0) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    GET {base}/openapi.json on a deployed chute (Bearer token).
    Many FastAPI chutes expose this for dynamic forms.
    """
    b = (base_url or "").strip().rstrip("/")
    if not is_allowed_chutes_deploy_base(b + "/"):
        return None, "Invalid base URL (need https://*.chutes.ai)."
    url = b + "/openapi.json"
    headers = {"Accept": "application/json"}
    k = (api_key or "").strip()
    if k:
        headers["Authorization"] = f"Bearer {k}"
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(2_000_000).decode("utf-8", errors="replace")
            return json.loads(raw), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read(2000).decode("utf-8", errors="replace")
        except OSError:
            body = str(e)
        return None, f"HTTP {e.code}: {body or e.reason}"
    except Exception as exc:
        return None, str(exc)


def build_target_url(base_url: str, path: str) -> Optional[str]:
    b = (base_url or "").strip().rstrip("/")
    p = (path or "").strip() or "/"
    if not p.startswith("/"):
        p = "/" + p
    if "\n" in p or "\r" in p or ".." in p:
        return None
    if not is_allowed_chutes_deploy_base(b + "/"):
        return None
    return b + p


def proxy_chute_call(
    api_key: str,
    base_url: str,
    path: str,
    method: str = "POST",
    json_body: Any = None,
    timeout: float = 180.0,
    max_bytes: int = 6_000_000,
) -> Tuple[bool, Dict[str, Any]]:
    key = (api_key or "").strip()
    if not key:
        return False, {"error": "Save an API key under Account first."}

    m = (method or "POST").upper().strip()
    if m not in ("GET", "POST", "PUT", "DELETE"):
        return False, {"error": "Method must be GET, POST, PUT, or DELETE."}

    target = build_target_url(base_url, path)
    if not target:
        return False, {"error": "Invalid base URL or path. Use https://…chutes.ai and a normal path."}

    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "*/*",
    }
    data: Optional[bytes] = None
    if m in ("POST", "PUT") and json_body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(json_body).encode("utf-8")

    req = urllib.request.Request(target, data=data, method=m, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                return False, {"error": f"Response larger than {max_bytes} bytes."}
            ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            out: Dict[str, Any] = {
                "status": resp.getcode(),
                "content_type": ct or "application/octet-stream",
            }
            if "application/json" in ct or ct.endswith("+json"):
                try:
                    out["json"] = json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    out["text"] = raw.decode("utf-8", errors="replace")[:50_000]
            elif ct.startswith("image/") or ct.startswith("audio/") or ct.startswith("video/"):
                out["data_base64"] = base64.standard_b64encode(raw).decode("ascii")
            else:
                try:
                    out["text"] = raw.decode("utf-8", errors="replace")[:50_000]
                except Exception:
                    out["data_base64"] = base64.standard_b64encode(raw).decode("ascii")
            return True, out
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read(8000).decode("utf-8", errors="replace")
        except OSError:
            err_body = str(e)
        try:
            j = json.loads(err_body)
            return False, {"status": e.code, "error": j}
        except json.JSONDecodeError:
            return False, {"status": e.code, "error": err_body or e.reason}
    except Exception as exc:
        return False, {"error": str(exc)}
