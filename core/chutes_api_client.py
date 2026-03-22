"""
HTTP client for the Chutes REST API (https://chutes.ai/docs/api-reference/overview).

Uses the API key from the manager; tries several Authorization styles (per platform docs).
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union


def auth_header_variants(api_key: str) -> List[Dict[str, str]]:
    """Header sets to try for authenticated requests."""
    key = api_key.strip()
    if not key:
        return []
    basic_b64 = base64.b64encode(f"{key}:".encode()).decode("ascii")
    return [
        {"Authorization": f"Bearer {key}", "Accept": "application/json"},
        {"Authorization": f"Basic {basic_b64}", "Accept": "application/json"},
        {"Authorization": f"Basic {key}", "Accept": "application/json"},
        {"X-API-Key": key, "Accept": "application/json"},
    ]


def _build_url(base_url: str, path: str, query: Optional[Mapping[str, Any]] = None) -> str:
    base = (base_url or "https://api.chutes.ai").rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    url = base + path
    if not query:
        return url
    pairs: List[Tuple[str, str]] = []
    for k, v in query.items():
        if v is None or v == "":
            continue
        if isinstance(v, bool):
            v = str(v).lower()
        pairs.append((str(k), str(v)))
    if pairs:
        url += "?" + urllib.parse.urlencode(pairs)
    return url


def _http_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[bytes] = None,
    timeout: float = 60.0,
) -> Tuple[int, str]:
    req = urllib.request.Request(url, method=method.upper(), headers=headers, data=body)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read(800_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read(8000).decode("utf-8", errors="replace") if e.fp else ""
        return e.code, raw
    except urllib.error.URLError as e:
        return -1, str(e.reason if hasattr(e, "reason") else e)


def api_get_public(base_url: str, path: str, query: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Unauthenticated GET (e.g. /ping, /pricing)."""
    url = _build_url(base_url, path, query)
    code, text = _http_request("GET", url, {"Accept": "application/json"})
    out: Dict[str, Any] = {"ok": code == 200, "status": code, "url": url}
    if code == 200:
        try:
            out["data"] = json.loads(text)
        except json.JSONDecodeError:
            out["data"] = text
    else:
        out["error"] = text[:2000]
    return out


def api_request_authenticated(
    method: str,
    base_url: str,
    path: str,
    api_key: str,
    *,
    query: Optional[Mapping[str, Any]] = None,
    json_body: Optional[Mapping[str, Any]] = None,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """
    Authenticated request. Tries each auth header variant until a non-401/403 response
    or success.
    """
    key = api_key.strip()
    url = _build_url(base_url, path, query)
    result: Dict[str, Any] = {
        "ok": False,
        "status": 0,
        "url": url,
        "method": method.upper(),
        "data": None,
        "error": "",
    }
    if not key:
        result["error"] = "No API key configured. Save one under Account / API key."
        result["status"] = -1
        return result

    body_bytes: Optional[bytes] = None
    extra: Dict[str, str] = {}
    if json_body is not None:
        body_bytes = json.dumps(json_body).encode("utf-8")
        extra["Content-Type"] = "application/json"

    last_code = 0
    last_text = ""
    for auth in auth_header_variants(key):
        headers = {**auth, **extra}
        code, text = _http_request(method.upper(), url, headers, body_bytes, timeout=timeout)
        last_code, last_text = code, text
        if code in (401, 403):
            continue
        result["status"] = code
        if 200 <= code < 300:
            result["ok"] = True
            if text.strip():
                try:
                    result["data"] = json.loads(text)
                except json.JSONDecodeError:
                    result["data"] = text
            else:
                result["data"] = None
            return result
        # Other errors: don't try other auth styles (likely not auth-related)
        result["error"] = text[:4000]
        return result

    result["status"] = last_code
    result["error"] = last_text[:4000] or "Unauthorized with all auth variants."
    return result


def api_get_authenticated(
    base_url: str,
    path: str,
    api_key: str,
    query: Optional[Mapping[str, Any]] = None,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    return api_request_authenticated(
        "GET", base_url, path, api_key, query=query, timeout=timeout
    )


def api_post_change_bt_auth(
    base_url: str,
    api_key: str,
    json_body: Mapping[str, Any],
    *,
    fingerprint: Optional[str] = None,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """
    POST /users/change_bt_auth — link Bittensor coldkey/hotkey to a website-created account.

    The API often expects ``Authorization`` to be the account **fingerprint** (Settings on
    chutes.ai), not a cpk API key. ``api_request_authenticated`` stops on the first non-401
    response, so a 422 from Bearer auth would block other styles; this helper tries several.
    """
    url = _build_url(base_url, "/users/change_bt_auth", None)
    body_bytes = json.dumps(dict(json_body)).encode("utf-8")
    result: Dict[str, Any] = {
        "ok": False,
        "status": 0,
        "url": url,
        "method": "POST",
        "data": None,
        "error": "",
    }

    attempts: List[Dict[str, str]] = []
    fp = (fingerprint or "").strip()
    if fp:
        for auth_val in (fp, f"Bearer {fp}", f"Basic {fp}"):
            attempts.append(
                {
                    "Authorization": auth_val,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
    for auth in auth_header_variants(api_key):
        if "Authorization" not in auth:
            continue
        attempts.append({**auth, "Content-Type": "application/json"})

    last_code = 0
    last_text = ""
    for headers in attempts:
        code, text = _http_request("POST", url, headers, body_bytes, timeout=timeout)
        last_code, last_text = code, text
        if 200 <= code < 300:
            result["ok"] = True
            result["status"] = code
            if text.strip():
                try:
                    result["data"] = json.loads(text)
                except json.JSONDecodeError:
                    result["data"] = text
            return result
        if code in (401, 403, 422):
            continue
        result["status"] = code
        result["error"] = text[:4000]
        return result

    result["status"] = last_code
    result["error"] = last_text[:4000] or "No successful auth variant."
    return result


def probe_chutes_api(api_key: str, base_url: str) -> Dict[str, object]:
    """
    Backwards-compatible probe: find a working GET list path + auth (for health checks).
    """
    key = api_key.strip()
    base = (base_url or "https://api.chutes.ai").rstrip("/")
    if not key:
        return {"ok": False, "error": "No API key provided."}

    paths = ["/chutes/", "/v1/chutes/", "/api/v1/chutes/"]
    last: Dict[str, Any] = {"status": 0, "error": ""}
    for path in paths:
        r = api_get_authenticated(base, path, key, {"limit": 1}, timeout=15.0)
        last = r
        if r.get("ok"):
            data = r.get("data")
            preview: Union[str, object]
            if isinstance(data, dict):
                preview = f"JSON keys: {list(data.keys())[:12]}"
            elif isinstance(data, list):
                preview = f"JSON list, len={len(data)}"
            else:
                preview = str(data)[:200] if data is not None else ""
            return {
                "ok": True,
                "status": r.get("status"),
                "url": r.get("url"),
                "preview": preview,
            }

    return {
        "ok": False,
        "status": last.get("status", 0),
        "error": (last.get("error") or "")[:400],
    }
