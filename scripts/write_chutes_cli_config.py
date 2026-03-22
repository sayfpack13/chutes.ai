#!/usr/bin/env python3
"""
Write ~/.chutes/config.ini for website-created accounts + local Bittensor wallet.

Reads:
  - API key from <repo>/.local/credentials.json (same as the dashboard)
  - Coldkey: ~/.bittensor/wallets/<coldkey>/coldkeypub.txt
  - Hotkey:  ~/.bittensor/wallets/<coldkey>/hotkeys/<hotkey>

Fetches user_id via GET /users/me or GET /users/user_id_lookup?username=...

Then run Chutes' account linking step (see docs):
  https://chutes.ai/docs/cli/website-account-update
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _strip_0x(seed: str) -> str:
    s = seed.strip()
    return s[2:] if s.lower().startswith("0x") else s


def _pick_user_id(data: object) -> str | None:
    if isinstance(data, str) and data.strip():
        return data.strip()
    if not isinstance(data, dict):
        return None
    for k in ("user_id", "id", "userId", "uid"):
        v = data.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _pick_username(data: object) -> str | None:
    if isinstance(data, dict):
        for k in ("username", "user_name", "name"):
            v = data.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Build ~/.chutes/config.ini from wallet + dashboard API key.")
    ap.add_argument(
        "--repo-root",
        type=Path,
        default=_repo_root(),
        help="chutes.ai repo root (default: parent of scripts/)",
    )
    ap.add_argument(
        "--wallets-root",
        type=Path,
        default=Path.home() / ".bittensor" / "wallets",
        help="Bittensor wallets directory",
    )
    ap.add_argument("--coldkey", type=str, default="", help="Coldkey folder name (default: only folder under wallets)")
    ap.add_argument("--hotkey", type=str, default="", help="Hotkey file name (default: single non-pub hotkey)")
    ap.add_argument("--username", type=str, default="", help="Chutes username if /users/me is unavailable")
    ap.add_argument(
        "--user-id",
        type=str,
        default="",
        help="Chutes user id if API lookup fails (from website profile or support)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print INI to stdout only")
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    sys.path.insert(0, str(repo))
    from core.chutes_api_client import api_get_authenticated
    from core.credentials_store import load_credentials

    creds = load_credentials(repo)
    key = creds.api_key.strip()
    if not key:
        print("No API key in .local/credentials.json — save one under Account first.", file=sys.stderr)
        return 1

    base = creds.effective_base_url()
    wallets = args.wallets_root
    if not wallets.is_dir():
        print(f"Wallets directory missing: {wallets}", file=sys.stderr)
        return 1

    cold_dirs = [p for p in wallets.iterdir() if p.is_dir()]
    if args.coldkey:
        cold = wallets / args.coldkey
    elif len(cold_dirs) == 1:
        cold = cold_dirs[0]
    else:
        print("Pass --coldkey NAME (multiple coldkey folders found).", file=sys.stderr)
        return 1

    coldkeypub = cold / "coldkeypub.txt"
    if not coldkeypub.is_file():
        print(f"Missing {coldkeypub}", file=sys.stderr)
        return 1
    cold_ss58 = str(_load_json(coldkeypub)["ss58Address"])

    hotkeys_dir = cold / "hotkeys"
    if not hotkeys_dir.is_dir():
        print(f"Missing {hotkeys_dir}", file=sys.stderr)
        return 1
    hot_files = [p for p in hotkeys_dir.iterdir() if p.is_file() and not p.name.endswith("pub.txt")]
    if args.hotkey:
        hot_path = hotkeys_dir / args.hotkey
    elif len(hot_files) == 1:
        hot_path = hot_files[0]
    else:
        print("Pass --hotkey NAME (multiple hotkey files found).", file=sys.stderr)
        return 1

    if not hot_path.is_file():
        print(f"Missing hotkey file {hot_path}", file=sys.stderr)
        return 1
    hot = _load_json(hot_path)
    hot_seed = _strip_0x(str(hot["secretSeed"]))
    hot_ss58 = str(hot["ss58Address"])
    hot_name = hot_path.name

    me = api_get_authenticated(base, "/users/me", key)
    username: str | None = None
    user_id: str | None = None
    if me.get("ok") and isinstance(me.get("data"), (dict, str)):
        user_id = _pick_user_id(me["data"])
        if isinstance(me["data"], dict):
            username = _pick_username(me["data"])
    if not user_id:
        uid_arg = (args.user_id or "").strip()
        if uid_arg:
            user_id = uid_arg
        else:
            uname = (args.username or username or "").strip()
            if not uname:
                print(
                    "Could not resolve user_id from GET /users/me. "
                    "Pass --username YOUR_CHUTES_USERNAME to use /users/user_id_lookup, "
                    "or pass --user-id ... explicitly.",
                    file=sys.stderr,
                )
                return 1
            lu = api_get_authenticated(base, "/users/user_id_lookup", key, query={"username": uname})
            if not lu.get("ok"):
                print(f"user_id_lookup failed: {lu.get('status')} {lu.get('error', '')[:500]}", file=sys.stderr)
                return 1
            user_id = _pick_user_id(lu.get("data"))
            username = username or uname

    if not user_id:
        print("Could not determine user_id from API response.", file=sys.stderr)
        return 1
    if not username:
        username = (args.username or "").strip() or "unknown"

    ini = (
        f"[api]\n"
        f"base_url = {base}\n\n"
        f"[auth]\n"
        f"username = {username}\n"
        f"user_id = {user_id}\n"
        f"hotkey_seed = {hot_seed}\n"
        f"hotkey_name = {hot_name}\n"
        f"hotkey_ss58address = {hot_ss58}\n\n"
        f"[payment]\n"
        f"address = {cold_ss58}\n"
    )

    if args.dry_run:
        print(ini, end="")
        return 0

    out_dir = Path.home() / ".chutes"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "config.ini"
    out_path.write_text(ini, encoding="utf-8")
    try:
        os.chmod(out_path, 0o600)
    except OSError:
        pass

    print(f"Wrote {out_path}")
    print("Next: link wallet to Chutes (required before `chutes build`):")
    print(f"  cd {repo} && .venv/bin/python scripts/link_chutes_bittensor.py")
    print("  https://chutes.ai/docs/cli/website-account-update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
