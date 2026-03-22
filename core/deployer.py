"""
Wrapper around the ``chutes`` CLI for build / deploy / status / logs.
"""

from __future__ import annotations

import json
import queue
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .credentials_store import subprocess_env_with_credentials

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent

# Chutes ``build`` uses ``input()`` for "show all files?" and "Confirm submitting build context?".
# Non-interactive runs must answer ``y`` or the process blocks forever.
_CHUTES_BUILD_STDIN_ANSWERS = b"y\ny\ny\n"


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
    *,
    stdin_input: Optional[bytes] = None,
) -> CommandResult:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT_DEFAULT
    exe = chutes_executable(root)
    if not exe:
        return _missing_chutes_result()
    env = subprocess_env_with_credentials(root)
    cmd = [exe, *args]
    run_kw: Dict[str, Any] = {
        "cwd": str(cwd) if cwd else None,
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "env": env,
    }
    if stdin_input is not None:
        run_kw["input"] = stdin_input
    proc = subprocess.run(cmd, **run_kw)
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
    # Include cwd so the chute module file is in the remote build context when Image has no .add().
    args.append("--include-cwd")
    # Image builds can take a long time
    return run_chutes(
        args,
        cwd=cwd,
        timeout=3600,
        repo_root=repo_root,
        stdin_input=_CHUTES_BUILD_STDIN_ANSWERS,
    )


def _pump_subprocess_stdout(stdout: Any, out_q: queue.Queue[Optional[bytes]]) -> None:
    try:
        while True:
            chunk = stdout.read(4096)
            if not chunk:
                break
            out_q.put(chunk)
    finally:
        out_q.put(None)


def _feed_chutes_build_prompts(stdin: Any, proc: subprocess.Popen) -> None:
    """Answer ``input()`` prompts from ``chutes build`` (non-interactive)."""
    time.sleep(0.05)
    try:
        for _ in range(10):
            if proc.poll() is not None:
                break
            try:
                stdin.write(b"y\n")
                stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                break
            time.sleep(0.12)
    finally:
        try:
            stdin.close()
        except OSError:
            pass


def iter_chutes_stream_ndjson(
    args: List[str],
    cwd: Optional[Path | str] = None,
    repo_root: Optional[Path | str] = None,
    timeout: Optional[int] = None,
    *,
    result_extras: Optional[Dict[str, object]] = None,
    auto_answer_build_prompts: bool = False,
) -> Iterator[str]:
    """
    Run ``chutes`` with merged stdout/stderr, yielding **NDJSON** lines (``\\n``-terminated).

    Uses **binary chunk reads** in a thread (not line iteration): the CLI often **fully
    buffers** stdout when not a TTY, so line-based streaming would appear “stuck” until exit.

    Each line is ``{"type":"log","message":"..."}`` or final
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
    # Prefer line-buffered stdio on GNU systems (helps when the subprocess uses libc stdio).
    if sys.platform != "win32" and shutil.which("stdbuf"):
        cmd: List[str] = ["stdbuf", "-oL", "-eL", exe, *args]
    else:
        cmd = [exe, *args]

    yield json.dumps(
        {
            "type": "log",
            "message": "[dashboard] Starting chutes (streaming output; first bytes may be delayed if the CLI buffers)…",
        }
    ) + "\n"

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE if auto_answer_build_prompts else subprocess.DEVNULL,
        bufsize=0,
    )
    accumulated: List[bytes] = []
    rc = -1
    assert proc.stdout is not None
    if auto_answer_build_prompts and proc.stdin:
        threading.Thread(
            target=_feed_chutes_build_prompts,
            args=(proc.stdin, proc),
            daemon=True,
        ).start()
    out_q: queue.Queue[Optional[bytes]] = queue.Queue()
    pump = threading.Thread(
        target=_pump_subprocess_stdout,
        args=(proc.stdout, out_q),
        daemon=True,
    )
    pump.start()

    t_start = time.monotonic()
    last_heartbeat = t_start
    try:
        while True:
            try:
                chunk = out_q.get(timeout=1.0)
            except queue.Empty:
                now = time.monotonic()
                if now - last_heartbeat >= 8.0:
                    elapsed = int(now - t_start)
                    yield json.dumps(
                        {
                            "type": "log",
                            "message": (
                                f"[dashboard] Still running… {elapsed}s. "
                                "If there is no output above yet, the Chutes CLI may be buffering "
                                "or waiting on the remote builder."
                            ),
                        }
                    ) + "\n"
                    last_heartbeat = now
                continue

            if chunk is None:
                break
            accumulated.append(chunk)
            last_heartbeat = time.monotonic()
            text = chunk.decode("utf-8", errors="replace")
            if text:
                yield json.dumps({"type": "log", "message": text}) + "\n"
    finally:
        try:
            proc.stdout.close()
        except OSError:
            pass
        pump.join(timeout=5.0)
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

    full = b"".join(accumulated).decode("utf-8", errors="replace")
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
    """Stream ``chutes build <ref> --wait --include-cwd`` as NDJSON lines."""
    return iter_chutes_stream_ndjson(
        ["build", module_ref, "--wait", "--include-cwd"],
        cwd=cwd,
        repo_root=repo_root,
        timeout=3600,
        result_extras={"ref": module_ref},
        auto_answer_build_prompts=True,
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
