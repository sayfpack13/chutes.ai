"""
Wrapper around the ``chutes`` CLI for build / deploy / status / logs.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .credentials_store import subprocess_env_with_credentials

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent


@dataclass
class CommandResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str


def chutes_executable() -> Optional[str]:
    """Return path to ``chutes`` on PATH, or None if not installed / not visible."""
    return shutil.which("chutes")


def chutes_on_path() -> bool:
    return chutes_executable() is not None


def _missing_chutes_result() -> CommandResult:
    msg = (
        "chutes CLI not found on PATH. Install with: pip install -r requirements-chutes.txt "
        "(or pip install chutes), then restart the terminal. "
        "On Windows you may need Visual C++ Build Tools for dependencies."
    )
    return CommandResult(ok=False, returncode=-1, stdout="", stderr=msg)


def run_chutes(
    args: List[str],
    cwd: Optional[Path | str] = None,
    timeout: Optional[int] = None,
    repo_root: Optional[Path | str] = None,
) -> CommandResult:
    exe = chutes_executable()
    if not exe:
        return _missing_chutes_result()
    root = Path(repo_root) if repo_root is not None else REPO_ROOT_DEFAULT
    env = subprocess_env_with_credentials(root)
    cmd = [exe, *args]
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return CommandResult(
        ok=proc.returncode == 0,
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def build_chute(
    module_ref: str,
    cwd: Path,
    wait: bool = True,
    repo_root: Optional[Path | str] = None,
) -> CommandResult:
    args = ["build", module_ref]
    if wait:
        args.append("--wait")
    # Image builds can take a long time
    return run_chutes(args, cwd=cwd, timeout=3600, repo_root=repo_root)


def deploy_chute(
    module_ref: str,
    cwd: Path,
    accept_fee: bool = True,
    repo_root: Optional[Path | str] = None,
) -> CommandResult:
    args = ["deploy", module_ref]
    if accept_fee:
        args.append("--accept-fee")
    return run_chutes(args, cwd=cwd, timeout=600, repo_root=repo_root)


def chutes_list(repo_root: Optional[Path | str] = None) -> CommandResult:
    return run_chutes(["chutes", "list"], timeout=120, repo_root=repo_root)


def chutes_get(name: str, repo_root: Optional[Path | str] = None) -> CommandResult:
    return run_chutes(["chutes", "get", name], timeout=120, repo_root=repo_root)


def chutes_logs(
    name: str,
    tail: int = 50,
    repo_root: Optional[Path | str] = None,
) -> CommandResult:
    return run_chutes(
        ["chutes", "logs", name, "--tail", str(tail)],
        timeout=120,
        repo_root=repo_root,
    )
