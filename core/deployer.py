"""
Wrapper around the ``chutes`` CLI for build / deploy / status / logs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .credentials_store import subprocess_env_with_credentials

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent


@dataclass
class CommandResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str


def chutes_executable(repo_root: Optional[Path | str] = None) -> Optional[str]:
    """Return path to ``chutes`` on PATH, or under ``<repo>/.venv`` if present."""
    found = shutil.which("chutes")
    if found:
        return found
    root = Path(repo_root) if repo_root is not None else REPO_ROOT_DEFAULT
    if sys.platform == "win32":
        candidate = root / ".venv" / "Scripts" / "chutes.exe"
    else:
        candidate = root / ".venv" / "bin" / "chutes"
    if candidate.is_file():
        return str(candidate)
    return None


def chutes_on_path(repo_root: Optional[Path | str] = None) -> bool:
    return chutes_executable(repo_root) is not None


def _missing_chutes_result() -> CommandResult:
    msg = (
        "chutes CLI not found. In the project venv run: pip install -r requirements-chutes.txt "
        "(or pip install chutes), then restart the dashboard process so PATH includes .venv/bin."
    )
    if sys.platform == "win32":
        msg += " On Windows, MSVC may be required if pip builds netifaces from source."
    return CommandResult(ok=False, returncode=-1, stdout="", stderr=msg)


def run_chutes(
    args: List[str],
    cwd: Optional[Path | str] = None,
    timeout: Optional[int] = None,
    repo_root: Optional[Path | str] = None,
) -> CommandResult:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT_DEFAULT
    exe = chutes_executable(root)
    if not exe:
        return _missing_chutes_result()
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


def iter_chutes_stream_ndjson(
    args: List[str],
    cwd: Optional[Path | str] = None,
    repo_root: Optional[Path | str] = None,
    timeout: Optional[int] = None,
    *,
    result_extras: Optional[Dict[str, object]] = None,
) -> Iterator[str]:
    """
    Run ``chutes`` with merged stdout/stderr, yielding **NDJSON** lines (``\\n``-terminated).

    Each line is a JSON object: ``{"type":"log","message":"..."}`` or final
    ``{"type":"result","ok":bool,"returncode":int,"stdout":"...","stderr":""}``.
    """
    root = Path(repo_root) if repo_root is not None else REPO_ROOT_DEFAULT
    exe = chutes_executable(root)
    if not exe:
        miss = _missing_chutes_result()
        yield json.dumps({"type": "log", "message": miss.stderr.strip()}) + "\n"
        res: Dict[str, object] = {
            "type": "result",
            "ok": False,
            "returncode": miss.returncode,
            "stdout": "",
            "stderr": miss.stderr,
        }
        if result_extras:
            res.update(result_extras)
        yield json.dumps(res) + "\n"
        return

    env = dict(subprocess_env_with_credentials(root))
    env.setdefault("PYTHONUNBUFFERED", "1")
    cmd = [exe, *args]
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    accumulated: List[str] = []
    rc = -1
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            accumulated.append(line)
            yield json.dumps({"type": "log", "message": line.rstrip("\r\n")}) + "\n"
    finally:
        try:
            proc.stdout.close()
        except OSError:
            pass
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            yield json.dumps(
                {"type": "log", "message": "[dashboard] command timed out"}
            ) + "\n"
            rc = -124

    full = "".join(accumulated)
    out: Dict[str, object] = {
        "type": "result",
        "ok": rc == 0,
        "returncode": rc,
        "stdout": full,
        "stderr": "",
    }
    if result_extras:
        out.update(result_extras)
    yield json.dumps(out) + "\n"


def iter_build_chute_stream(
    module_ref: str,
    cwd: Path,
    repo_root: Optional[Path | str] = None,
) -> Iterator[str]:
    """Stream ``chutes build <ref> --wait`` as NDJSON lines."""
    return iter_chutes_stream_ndjson(
        ["build", module_ref, "--wait"],
        cwd=cwd,
        repo_root=repo_root,
        timeout=3600,
        result_extras={"ref": module_ref},
    )


def iter_deploy_chute_stream(
    module_ref: str,
    cwd: Path,
    repo_root: Optional[Path | str] = None,
) -> Iterator[str]:
    """Stream ``chutes deploy <ref> --accept-fee`` as NDJSON lines."""
    return iter_chutes_stream_ndjson(
        ["deploy", module_ref, "--accept-fee"],
        cwd=cwd,
        repo_root=repo_root,
        timeout=600,
        result_extras={"ref": module_ref},
    )


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
