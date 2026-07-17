from __future__ import annotations

from pathlib import Path

from ..config import load_config, validate_config
from ..diagnostics import Diagnostic


def run(repository_root: Path, config_path: str) -> list[Diagnostic]:
    try:
        config = load_config(repository_root, config_path)
    except Exception as exc:  # normalized CLI diagnostic
        return [Diagnostic("error", "CONFIG_LOAD", str(exc), config_path)]
    return validate_config(repository_root, config)
