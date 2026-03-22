#!/usr/bin/env python3
"""
Chutes AI Manager — CLI for configs, code generation, and deploy helpers.

Run from the repository root:

  python cli.py --help
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import (  # noqa: E402
    ConfigManager,
    ChuteConfig,
    build_chute,
    chutes_get,
    chutes_list,
    chutes_logs,
    deploy_chute,
    get_template,
    get_template_names,
    module_ref,
    seed_builtin_templates,
    write_chute_module,
)


def _manager() -> ConfigManager:
    return ConfigManager(str(ROOT / "configs"))


def cmd_seed(_args: argparse.Namespace) -> int:
    paths = seed_builtin_templates(ROOT)
    print(f"Wrote {len(paths)} template YAML files under configs/templates/")
    for p in paths:
        print(f"  - {p.relative_to(ROOT)}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    m = _manager()
    try:
        data = get_template(args.template)
    except ValueError as e:
        print(e, file=sys.stderr)
        print("Available:", ", ".join(get_template_names()), file=sys.stderr)
        return 1
    data["name"] = args.name
    if args.username:
        data["username"] = args.username
    cfg = ChuteConfig(**data)
    out = m.save_config(cfg)
    print(f"Saved {out.relative_to(ROOT)}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    m = _manager()
    names = args.names
    if args.all:
        names = m.list_configs()
    if not names:
        print("No configs specified. Use names or --all.", file=sys.stderr)
        return 1
    code_dir = ROOT / "chute_packages"
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / "__init__.py").write_text(
        '"""Generated Chute modules for `chutes build` / `chutes deploy`."""\n',
        encoding="utf-8",
    )
    for name in names:
        cfg = m.load_config(name)
        path = write_chute_module(cfg, ROOT)
        print(f"Generated {path.relative_to(ROOT)}  ({module_ref(cfg)})")
    print("\nBuild from chute_packages directory:")
    print(f"  cd chute_packages")
    print(f"  chutes build {module_ref(m.load_config(names[0]))} --wait")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    m = _manager()
    cfg = m.load_config(args.name)
    ref = module_ref(cfg)
    cwd = ROOT / "chute_packages"
    if not cwd.is_dir():
        print("chute_packages/ missing. Run: python cli.py generate", args.name, file=sys.stderr)
        return 1
    print(f"Running: chutes build {ref} --wait (cwd={cwd})")
    res = build_chute(ref, cwd=cwd, wait=True)
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    return 0 if res.ok else res.returncode


def cmd_deploy(args: argparse.Namespace) -> int:
    m = _manager()
    cfg = m.load_config(args.name)
    ref = module_ref(cfg)
    cwd = ROOT / "chute_packages"
    print(f"Running: chutes deploy {ref} (cwd={cwd})")
    res = deploy_chute(ref, cwd=cwd, accept_fee=not args.no_accept_fee)
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    return 0 if res.ok else res.returncode


def cmd_status(_args: argparse.Namespace) -> int:
    res = chutes_list()
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    return 0 if res.ok else res.returncode


def cmd_logs(args: argparse.Namespace) -> int:
    res = chutes_logs(args.name, tail=args.tail)
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    return 0 if res.ok else res.returncode


def cmd_get(args: argparse.Namespace) -> int:
    res = chutes_get(args.name)
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    return 0 if res.ok else res.returncode


def main() -> int:
    p = argparse.ArgumentParser(description="Chutes AI config & deploy helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("seed-templates", help="Write built-in YAML templates to configs/templates/")
    sp.set_defaults(func=cmd_seed)

    sp = sub.add_parser("new", help="Create configs/<name>.yaml from a built-in template key")
    sp.add_argument("template", help="Template key: " + ", ".join(get_template_names()))
    sp.add_argument("name", help="New chute config name (slug)")
    sp.add_argument("--username", help="Chutes.ai username", default="")
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("generate", help="Generate Python modules into chute_packages/")
    sp.add_argument("names", nargs="*", help="Config names (without .yaml)")
    sp.add_argument("--all", action="store_true", help="Generate all configs")
    sp.set_defaults(func=cmd_generate)

    sp = sub.add_parser("build", help="chutes build <module>:chute --wait in chute_packages/")
    sp.add_argument("name", help="Config name")
    sp.set_defaults(func=cmd_build)

    sp = sub.add_parser("deploy", help="chutes deploy <module>:chute in chute_packages/")
    sp.add_argument("name", help="Config name")
    sp.add_argument(
        "--no-accept-fee",
        action="store_true",
        help="Omit --accept-fee (you may get HTTP 402)",
    )
    sp.set_defaults(func=cmd_deploy)

    sp = sub.add_parser("status", help="Run: chutes chutes list")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("logs", help="Run: chutes chutes logs")
    sp.add_argument("name", help="Chute name on platform")
    sp.add_argument("--tail", type=int, default=50)
    sp.set_defaults(func=cmd_logs)

    sp = sub.add_parser("get", help="Run: chutes chutes get <name>")
    sp.add_argument("name", help="Chute name on platform")
    sp.set_defaults(func=cmd_get)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
