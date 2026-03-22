"""Normalize Chutes list API rows for the playground catalog (grouped by template)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

TEMPLATE_ORDER = (
    "llm",
    "vllm",
    "sglang",
    "image_generation",
    "diffusion",
    "image",
    "video",
    "tts",
    "text_to_speech",
    "speech_to_text",
    "speech",
    "music_generation",
    "music",
    "embeddings",
    "embedding",
    "content_moderation",
    "other",
    "custom",
)

TEMPLATE_LABELS: Dict[str, str] = {
    "llm": "LLM",
    "vllm": "LLM (vLLM)",
    "sglang": "LLM (SGLang)",
    "image_generation": "Image Generation",
    "diffusion": "Image / diffusion",
    "image": "Image",
    "video": "Video",
    "tts": "Text to Speech",
    "text_to_speech": "Text to Speech",
    "speech_to_text": "Speech to Text",
    "speech": "Speech",
    "music_generation": "Music Generation",
    "music": "Music",
    "embeddings": "Embeddings",
    "embedding": "Embeddings",
    "content_moderation": "Content Moderation",
    "other": "Other",
    "custom": "Custom",
}

# Map common type names from API to normalized keys
TYPE_ALIASES: Dict[str, str] = {
    "image generation": "image_generation",
    "text to speech": "text_to_speech",
    "speech to text": "speech_to_text",
    "music generation": "music_generation",
    "content moderation": "content_moderation",
    "generativelanguage": "llm",
    "chat": "llm",
    "completion": "llm",
}


def pick_chute_rows(data: Any) -> List[Dict[str, Any]]:
    if not data:
        return []
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("items", "results", "chutes", "data"):
            v = data.get(key)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
    return []


def guess_base_url(row: Dict[str, Any]) -> Optional[str]:
    # 1. Explicit URL fields from API (highest priority)
    for k in ("public_api_base", "api_base", "base_url", "url", "endpoint", "api_url"):
        v = row.get(k)
        if isinstance(v, str) and v.strip().startswith("https://") and "chutes.ai" in v:
            return v.strip().rstrip("/")

    # Extract common fields
    user = (
        row.get("username")
        or row.get("user_name")
        or row.get("owner_username")
        or row.get("author")
        or ""
    )
    if not isinstance(user, str):
        user = str(user or "")
    user = user.strip()

    name = row.get("name") or row.get("slug") or row.get("chute_name") or ""
    if not isinstance(name, str):
        name = str(name or "")
    name = name.strip()
    
    slug = row.get("slug") or ""
    if not isinstance(slug, str):
        slug = str(slug or "")
    slug = slug.strip()
    
    chute_id = row.get("chute_id") or row.get("id") or ""

    # Build slug from name: "stabilityai/stable-diffusion-xl-base-1.0" -> "stabilityai-stable-diffusion-xl-base-1-0"
    def make_slug(s: str) -> str:
        return s.replace("/", "-").replace(" ", "-").replace(".", "-").replace("_", "-").lower().strip("-")

    # Check if this looks like a Chutes-hosted model (public chutes often use chutes-{slug}.chutes.ai)
    is_chutes_hosted = (
        row.get("public") is True
        or row.get("is_public") is True
        or (not user and name)
    )

    # 2. User-owned chute: {username}-{slug}.chutes.ai
    if user and slug:
        return f"https://{user.lower()}-{make_slug(slug)}.chutes.ai"
    if user and name:
        return f"https://{user.lower()}-{make_slug(name)}.chutes.ai"

    # 3. Chutes-hosted public models: chutes-{name}.chutes.ai
    # Examples: z-image-turbo -> chutes-z-image-turbo.chutes.ai
    #           FLUX.1-schnell -> chutes-flux-1-schnell.chutes.ai
    if name:
        base_slug = make_slug(name)
        # Try chutes-{slug}.chutes.ai pattern for Chutes-hosted models
        return f"https://chutes-{base_slug}.chutes.ai"

    # 4. Last resort: chute_id based URL (some chutes use this pattern)
    if chute_id:
        return f"https://chutes-{str(chute_id).lower()}.chutes.ai"

    return None


def normalize_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    base_url = guess_base_url(row)
    if not base_url:
        return None

    # Determine template/type
    tmpl = (
        row.get("standard_template")
        or row.get("chute_type")
        or row.get("template")
        or row.get("type")
        or "other"
    )
    if not isinstance(tmpl, str):
        tmpl = str(tmpl or "other")
    tmpl_key = tmpl.strip().lower() or "other"
    # Apply aliases
    tmpl_key = TYPE_ALIASES.get(tmpl_key, tmpl_key)

    tag = row.get("tagline") or row.get("description") or ""
    if not isinstance(tag, str):
        tag = str(tag or "")
    name = row.get("name") or row.get("slug") or "Chute"
    if not isinstance(name, str):
        name = str(name)
    slug = row.get("slug") or ""
    if not isinstance(slug, str):
        slug = str(slug or "")

    # Price/hot-cold info for display
    price = row.get("price_per_hour") or row.get("price") or row.get("hourly_price")
    if price is not None and not isinstance(price, (int, float)):
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = None
    is_hot = row.get("hot") or row.get("is_hot") or row.get("status") == "hot"

    return {
        "name": name,
        "slug": slug,
        "tagline": tag[:240],
        "template": tmpl_key,
        "public": bool(row.get("public") or row.get("is_public")),
        "chute_id": row.get("chute_id") or row.get("id"),
        "base_url": base_url,
        "price_per_hour": price,
        "hot": bool(is_hot),
    }


def group_catalog(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        t = str(r.get("template") or "other")
        buckets.setdefault(t, []).append(r)

    def sort_key(tid: str) -> int:
        try:
            return TEMPLATE_ORDER.index(tid)
        except ValueError:
            return 999

    out: List[Dict[str, Any]] = []
    for tid in sorted(buckets.keys(), key=sort_key):
        label = TEMPLATE_LABELS.get(tid, tid.replace("_", " ").title())
        items = sorted(buckets[tid], key=lambda x: str(x.get("name") or "").lower())
        out.append({"id": tid, "label": label, "chutes": items})
    return out
