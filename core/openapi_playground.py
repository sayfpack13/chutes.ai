"""
Map OpenAPI 3.x request bodies to dashboard playground field metadata (shared by image + chute tools).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def resolve_ref(openapi: Dict[str, Any], ref: str) -> Dict[str, Any]:
    if not ref.startswith("#/"):
        return {}
    cur: Any = openapi
    for part in ref[2:].split("/"):
        if not isinstance(cur, dict) or part not in cur:
            return {}
        cur = cur[part]
    return cur if isinstance(cur, dict) else {}


def normalize_schema_type(spec: Dict[str, Any]) -> str:
    t = spec.get("type")
    if isinstance(t, list):
        for x in t:
            if x and x != "null":
                return str(x)
        return "string"
    if t:
        return str(t)
    if "enum" in spec:
        return "string"
    if spec.get("oneOf") or spec.get("anyOf"):
        return "json"
    return "string"


def schema_to_field(
    key: str,
    spec: Dict[str, Any],
    openapi: Dict[str, Any],
    required: bool,
) -> Optional[Dict[str, Any]]:
    if not isinstance(spec, dict):
        return None
    if "$ref" in spec:
        spec = resolve_ref(openapi, spec["$ref"])
    if not spec:
        return None
    if spec.get("oneOf") or spec.get("anyOf"):
        return {
            "key": key,
            "title": spec.get("title") or key.replace("_", " ").title(),
            "type": "json",
            "required": required,
            "default": None,
            "description": spec.get("description", ""),
            "widget": "json",
        }
    if spec.get("type") == "object" or spec.get("type") == "array":
        return {
            "key": key,
            "title": spec.get("title") or key.replace("_", " ").title(),
            "type": "json",
            "required": required,
            "default": spec.get("default"),
            "description": spec.get("description", ""),
            "widget": "json",
        }
    typ = normalize_schema_type(spec)
    long_text_keys = (
        "prompt",
        "negative_prompt",
        "caption",
        "description",
        "text",
        "content",
        "input",
        "readme",
    )
    widget = (
        "textarea"
        if key.lower() in long_text_keys or "prompt" in key.lower()
        else "input"
    )
    field: Dict[str, Any] = {
        "key": key,
        "title": spec.get("title") or key.replace("_", " ").title(),
        "type": typ,
        "required": required,
        "default": spec.get("default"),
        "description": spec.get("description", ""),
        "enum": spec.get("enum"),
        "minimum": spec.get("minimum"),
        "maximum": spec.get("maximum"),
        "widget": widget,
    }
    if typ == "integer":
        field["step"] = 1
    if typ == "number":
        field["step"] = 0.1
    if key == "model" and typ == "string":
        if not (isinstance(spec.get("enum"), list) and len(spec["enum"]) > 0):
            field["widget"] = "model_select"
    if isinstance(spec.get("type"), list) and "null" in spec["type"]:
        field["nullable"] = True
    return field


def merge_schema_with_allof(openapi: Dict[str, Any], resolved: Dict[str, Any]) -> Dict[str, Any]:
    if not resolved.get("allOf"):
        return resolved
    merged: Dict[str, Any] = {"properties": {}, "required": []}
    for part in resolved["allOf"]:
        if "$ref" in part:
            part = resolve_ref(openapi, part["$ref"])
        if not isinstance(part, dict):
            continue
        props = part.get("properties") or {}
        merged["properties"].update(props)
        merged["required"] = list(merged["required"]) + list(part.get("required") or [])
    return merged


def resolve_request_schema(openapi: Dict[str, Any], operation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rb = operation.get("requestBody") or {}
    content = rb.get("content") or {}
    schema_block = None
    for ct, body in content.items():
        if "json" in ct.lower() and isinstance(body, dict):
            schema_block = body.get("schema")
            break
    if not schema_block:
        return None
    if "$ref" in schema_block:
        resolved = resolve_ref(openapi, schema_block["$ref"])
    else:
        resolved = schema_block
    if not resolved:
        return None
    return merge_schema_with_allof(openapi, resolved)


def properties_to_fields(
    openapi: Dict[str, Any],
    resolved: Dict[str, Any],
) -> Optional[List[Dict[str, Any]]]:
    props = resolved.get("properties") or {}
    if not props:
        return None
    req = set(resolved.get("required") or [])
    out: List[Dict[str, Any]] = []
    for key in sorted(props.keys(), key=lambda k: (k not in req, k)):
        f = schema_to_field(key, props[key], openapi, key in req)
        if f:
            out.append(f)
    return out or None


def extract_fields_for_operation(
    openapi: Dict[str, Any],
    path_key: str,
    method: str,
) -> Optional[List[Dict[str, Any]]]:
    m = (method or "post").lower()
    paths = openapi.get("paths") or {}
    methods = paths.get(path_key)
    if not isinstance(methods, dict):
        return None
    op = methods.get(m)
    if not isinstance(op, dict):
        return None
    resolved = resolve_request_schema(openapi, op)
    if not resolved:
        return None
    return properties_to_fields(openapi, resolved)


def list_json_body_operations(
    openapi: Dict[str, Any],
    *,
    max_ops: int = 100,
) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    paths = openapi.get("paths") or {}
    for path_key, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for meth in ("post", "put", "patch"):
            if len(out) >= max_ops:
                out.sort(key=lambda x: (x["path"], x["method"]))
                return out
            op = methods.get(meth)
            if not isinstance(op, dict):
                continue
            rb = op.get("requestBody")
            if not rb:
                continue
            content = (rb or {}).get("content") or {}
            if not any("json" in str(ct).lower() for ct in content):
                continue
            summary = (
                (op.get("summary") or "").strip()
                or (op.get("operationId") or "").strip()
                or f"{meth.upper()} {path_key}"
            )
            out.append(
                {
                    "path": path_key,
                    "method": meth.upper(),
                    "summary": summary[:200],
                }
            )
    out.sort(key=lambda x: (x["path"], x["method"]))
    return out


def find_post_operation_by_path_tail(openapi: Dict[str, Any], tail: str) -> Optional[Dict[str, Any]]:
    paths = openapi.get("paths") or {}
    for path_key, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        if str(path_key).rstrip("/").split("/")[-1] != tail:
            continue
        post = methods.get("post")
        if isinstance(post, dict):
            return post
    return None


def extract_image_generate_fields(openapi: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    post = find_post_operation_by_path_tail(openapi, "generate")
    if not post:
        return None
    resolved = resolve_request_schema(openapi, post)
    if not resolved:
        return None
    return properties_to_fields(openapi, resolved)
