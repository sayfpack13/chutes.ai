"""
Wrapper around the ``chutes`` CLI for build / deploy / status / logs.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class CommandResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str


def _which_chutes() -> str:
    path = shutil.which("chutes")
    if not path:
        raise FileNotFoundError(
            "chutes CLI not found on PATH. Install with: pip install chutes"
        )
    return path


def run_chutes(
    args: List[str],
    cwd: Optional[Path | str] = None,
    timeout: Optional[int] = None,
) -> CommandResult:
    cmd = [_which_chutes(), *args]
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return CommandResult(
        ok=proc.returncode == 0,
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def build_chute(module_ref: str, cwd: Path, wait: bool = True) -> CommandResult:
    args = ["build", module_ref]
    if wait:
        args.append("--wait")
    # Image builds can take a long time
    return run_chutes(args, cwd=cwd, timeout=3600)


def deploy_chute(module_ref: str, cwd: Path, accept_fee: bool = True) -> CommandResult:
    args = ["deploy", module_ref]
    if accept_fee:
        args.append("--accept-fee")
    return run_chutes(args, cwd=cwd, timeout=600)


def chutes_list() -> CommandResult:
    return run_chutes(["chutes", "list"], timeout=120)


def chutes_get(name: str) -> CommandResult:
    return run_chutes(["chutes", "get", name], timeout=120)


def chutes_logs(name: str, tail: int = 50) -> CommandResult:
    return run_chutes(["chutes", "logs", name, "--tail", str(tail)], timeout=120)
