"""Write built-in template dicts to configs/templates/*.yaml."""

from __future__ import annotations

from pathlib import Path

from .config_manager import ChuteConfig, ConfigManager
from .templates import TEMPLATES


def seed_builtin_templates(repo_root: Path | str) -> list[Path]:
    """Persist Python template definitions as YAML under configs/templates/."""
    manager = ConfigManager(str(Path(repo_root) / "configs"))
    written: list[Path] = []
    for _key, getter in TEMPLATES.items():
        cfg = ChuteConfig(**getter())
        written.append(manager.save_template(cfg))
    return written
