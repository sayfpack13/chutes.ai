"""
Resolve default Bittensor coldkey / hotkey SS58 addresses from ``~/.bittensor/wallets``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_bittensor_ss58(
    *,
    wallets_root: Optional[Path] = None,
    coldkey: str = "",
    hotkey: str = "",
) -> Tuple[Optional[str], Optional[str], str]:
    """
    Return ``(coldkey_ss58, hotkey_ss58, error_message)``.
    On success, ``error_message`` is empty.
    """
    root = wallets_root or (Path.home() / ".bittensor" / "wallets")
    if not root.is_dir():
        return None, None, f"Bittensor wallets directory not found: {root}"

    cold_dirs = [p for p in root.iterdir() if p.is_dir()]
    if coldkey:
        cold = root / coldkey
    elif len(cold_dirs) == 1:
        cold = cold_dirs[0]
    else:
        return None, None, "Multiple coldkey folders: pass coldkey name explicitly."

    ck = cold / "coldkeypub.txt"
    if not ck.is_file():
        return None, None, f"Missing coldkey public file: {ck}"

    hk_dir = cold / "hotkeys"
    if not hk_dir.is_dir():
        return None, None, f"Missing hotkeys directory: {hk_dir}"

    hot_files = [p for p in hk_dir.iterdir() if p.is_file() and not p.name.endswith("pub.txt")]
    if hotkey:
        hp = hk_dir / hotkey
    elif len(hot_files) == 1:
        hp = hot_files[0]
    else:
        return None, None, "Multiple hotkey files: pass hotkey name explicitly."

    if not hp.is_file():
        return None, None, f"Missing hotkey file: {hp}"

    try:
        cold_ss58 = str(_load_json(ck)["ss58Address"])
        hot_ss58 = str(_load_json(hp)["ss58Address"])
    except (KeyError, json.JSONDecodeError, TypeError) as e:
        return None, None, f"Invalid wallet JSON: {e}"

    return cold_ss58, hot_ss58, ""
