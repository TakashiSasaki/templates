"""Verify the selected local Policy distribution before execution."""
import hashlib
import re
from pathlib import Path

import yaml


def check_policy_distribution(root: Path) -> None:
    """Check the selected local distribution's closed lock before executing it."""
    try:
        config = yaml.safe_load((root / ".agent-policy.yml").read_text())
        lock = yaml.safe_load((root / ".agent-policy.lock").read_text())
        if not isinstance(config, dict) or not isinstance(lock, dict):
            raise ValueError("configuration and lock must be mappings")
        toolchain = config.get("toolchain")
        if (not isinstance(toolchain, dict)
                or toolchain.get("repository") != "TakashiSasaki/templates"
                or not isinstance(toolchain.get("revision"), str)
                or not re.fullmatch(r"[0-9a-f]{40}", toolchain["revision"])
                or lock.get("toolchain") != toolchain
                or type(lock.get("lock_version")) is not int
                or lock["lock_version"] != 1):
            raise ValueError("configuration/lock toolchain identity mismatch")
        required = {
            "inputs": {".agent-policy.yml"},
            "outputs": {
                ".agents/skills/maintain-progressive-discovery/SKILL.md",
                ".agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py",
            },
        }
        for section, required_paths in required.items():
            entries = lock.get(section)
            if not isinstance(entries, dict) or not required_paths.issubset(entries):
                raise ValueError(f"missing required {section}")
            for relative, identity in entries.items():
                if (not isinstance(relative, str) or not relative
                        or Path(relative).is_absolute()
                        or Path(relative).as_posix() != relative
                        or any(part in (".", "..") for part in relative.split("/"))):
                    raise ValueError("noncanonical lock path")
                target = root
                for part in Path(relative).parts:
                    target = target / part
                    if target.is_symlink():
                        raise ValueError("symlink in lock path")
                if (not isinstance(identity, dict)
                        or not isinstance(identity.get("sha256"), str)
                        or not re.fullmatch(r"[0-9a-f]{64}", identity["sha256"])
                        or hashlib.sha256(target.read_bytes()).hexdigest() != identity["sha256"]):
                    raise ValueError(f"stale {section}: {relative}")
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        raise ValueError(f"Policy distribution is invalid: {exc}") from exc

