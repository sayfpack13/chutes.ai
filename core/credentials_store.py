"""
Store Chutes API credentials locally under ``.local/`` (gitignored).

Used by the dashboard and by ``run_chutes`` to pass auth to the CLI / API.
See: https://chutes.ai/docs/cli/account
API reference: https://chutes.ai/docs/api-reference/overview
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ManagerCredentials(BaseModel):
    model_config = ConfigDict(extra="ignore")

    """Credentials managed by this repo (not the same as ~/.chutes/config.ini wallet auth)."""

    api_key: str = Field(default="", description="Secret from chutes keys create (often cpk_...)")
    api_base_url: str = Field(default="https://api.chutes.ai")
    # If set, CHUTES_CONFIG_PATH points here and we do not synthesize a minimal ini.
    chutes_config_path: str = Field(default="", description="Optional path to your config.ini")
    # Shown on chutes.ai Settings; required for POST /users/change_bt_auth from a website account.
    account_fingerprint: str = Field(default="", description="Account fingerprint (wallet link / some API calls)")

    def effective_base_url(self) -> str:
        return (self.api_base_url or "https://api.chutes.ai").rstrip("/")


def local_dir(repo_root: Path | str) -> Path:
    d = Path(repo_root) / ".local"
    d.mkdir(parents=True, exist_ok=True)
    return d


def credentials_path(repo_root: Path | str) -> Path:
    return local_dir(repo_root) / "credentials.json"


def generated_cli_config_path(repo_root: Path | str) -> Path:
    return local_dir(repo_root) / "chutes_config.ini"


def load_credentials(repo_root: Path | str) -> ManagerCredentials:
    path = credentials_path(repo_root)
    if not path.is_file():
        return ManagerCredentials()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return ManagerCredentials(**data)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return ManagerCredentials()


def save_credentials(repo_root: Path | str, creds: ManagerCredentials) -> None:
    path = credentials_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        creds.model_dump_json(indent=2),
        encoding="utf-8",
    )
    # Restrictive permissions on Unix (ignored on Windows)
    try:
        os.chmod(path, 0o600)
    except (OSError, AttributeError):
        pass


def mask_api_key(key: str, keep: int = 6) -> str:
    key = key.strip()
    if len(key) <= keep * 2:
        return "(set)" if key else "(empty)"
    return f"{key[:keep]}…{key[-keep:]}"


def write_minimal_chutes_ini(repo_root: Path | str, creds: ManagerCredentials) -> Optional[Path]:
    """
    Write a minimal config.ini (API key + base URL) under ``.local/`` for reference or ad‑hoc tools.

    The official ``chutes`` CLI does **not** use this for build/deploy: it needs a full
    ``~/.chutes/config.ini`` from ``chutes register`` (``user_id``, hotkey fields, etc.).
    """
    key = creds.api_key.strip()
    if not key or creds.chutes_config_path.strip():
        return None
    out = generated_cli_config_path(repo_root)
    base = creds.effective_base_url()
    text = (
        f"[api]\n"
        f"base_url = {base}\n\n"
        f"[auth]\n"
        f"api_key = {key}\n"
    )
    out.write_text(text, encoding="utf-8")
    try:
        os.chmod(out, 0o600)
    except (OSError, AttributeError):
        pass
    return out


def subprocess_env_with_credentials(repo_root: Path | str) -> dict[str, str]:
    """
    Environment variables for ``chutes`` subprocess calls.

    Never points ``CHUTES_CONFIG_PATH`` at the generated minimal ``.local/chutes_config.ini``:
    current Chutes requires ``[auth]`` keys such as ``user_id`` and hotkey material from
    ``chutes register``. Use the user's explicit path or ``~/.chutes/config.ini`` when present.
    """
    env = dict(os.environ)
    creds = load_credentials(repo_root)
    base = creds.effective_base_url()
    env["CHUTES_API_URL"] = base

    cfg_path = creds.chutes_config_path.strip()
    if cfg_path:
        env["CHUTES_CONFIG_PATH"] = cfg_path
    else:
        home_ini = Path.home() / ".chutes" / "config.ini"
        if home_ini.is_file():
            env["CHUTES_CONFIG_PATH"] = str(home_ini.resolve())

    key = creds.api_key.strip()
    if key:
        # Several tools accept one of these; harmless if ignored.
        env["CHUTES_API_KEY"] = key
        env["CHUTES_TOKEN"] = key

    return env


def parse_settings_form(
    api_key: str,
    api_base_url: str,
    chutes_config_path: str,
    existing: ManagerCredentials,
    clear_key: bool = False,
    account_fingerprint: str = "",
    clear_fingerprint: bool = False,
) -> ManagerCredentials:
    """Empty api_key means keep existing unless clear_key."""
    key = (api_key or "").strip()
    if clear_key:
        key = ""
    elif not key:
        key = existing.api_key

    url = (api_base_url or "").strip() or existing.api_base_url or "https://api.chutes.ai"
    cfg = (chutes_config_path or "").strip()

    fp = (account_fingerprint or "").strip()
    if clear_fingerprint:
        fp = ""
    elif not fp:
        fp = existing.account_fingerprint

    return ManagerCredentials(
        api_key=key,
        api_base_url=url,
        chutes_config_path=cfg,
        account_fingerprint=fp,
    )
