#!/usr/bin/env python3
"""
Link your Chutes (website) account to a local Bittensor coldkey + hotkey.

Required after writing ~/.chutes/config.ini if `chutes build` fails with:
  Could not find user with hotkey: ...

Calls POST /users/change_bt_auth (see Chutes docs):
  https://chutes.ai/docs/cli/website-account-update

Uses the dashboard API key from .local/credentials.json and, for most website accounts,
the **account fingerprint** from Chutes → Settings (or env ``CHUTES_FINGERPRINT``).

The same flow is available in the web UI: Account → Advanced → Link Bittensor wallet.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description="POST /users/change_bt_auth for website + wallet accounts.")
    ap.add_argument("--repo-root", type=Path, default=_repo_root())
    ap.add_argument("--wallets-root", type=Path, default=Path.home() / ".bittensor" / "wallets")
    ap.add_argument("--coldkey", type=str, default="")
    ap.add_argument("--hotkey", type=str, default="")
    ap.add_argument(
        "--fingerprint",
        type=str,
        default="",
        help="Account fingerprint from chutes.ai settings (or set CHUTES_FINGERPRINT)",
    )
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    sys.path.insert(0, str(repo))
    from core.bittensor_wallet import resolve_bittensor_ss58
    from core.chutes_api_client import api_post_change_bt_auth
    from core.credentials_store import load_credentials

    creds = load_credentials(repo)
    key = creds.api_key.strip()
    if not key:
        print("No API key in .local/credentials.json.", file=sys.stderr)
        return 1

    cold_ss58, hot_ss58, err = resolve_bittensor_ss58(
        wallets_root=args.wallets_root,
        coldkey=(args.coldkey or "").strip(),
        hotkey=(args.hotkey or "").strip(),
    )
    if err:
        print(err, file=sys.stderr)
        return 1

    fp = (args.fingerprint or os.environ.get("CHUTES_FINGERPRINT") or creds.account_fingerprint or "").strip()
    if not fp:
        print(
            "Fingerprint required: set in dashboard Account → Advanced, or pass --fingerprint, "
            "or export CHUTES_FINGERPRINT.",
            file=sys.stderr,
        )
        return 1

    base = creds.effective_base_url()
    body = {"coldkey": cold_ss58, "hotkey": hot_ss58}
    r = api_post_change_bt_auth(
        base,
        key,
        body,
        fingerprint=fp,
        timeout=60.0,
    )
    if r.get("ok"):
        print("Linked coldkey + hotkey to your Chutes account. Retry `chutes build`.")
        if r.get("data") is not None:
            print(json.dumps(r["data"], indent=2)[:2000])
        return 0

    print(f"HTTP {r.get('status')}", file=sys.stderr)
    print(r.get("error") or r.get("data") or "", file=sys.stderr)
    print(
        "\nSee: https://chutes.ai/docs/cli/website-account-update\n"
        "Use Settings → Fingerprint with --fingerprint (not the 'google' label).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
