from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/agent-policy/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_bootstrap() -> ModuleType:
    path = SCRIPTS / "bootstrap.py"
    spec = importlib.util.spec_from_file_location(
        "agent_policy_skill_primary_selection_bootstrap", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bootstrap = load_bootstrap()


def migration_inspection(*sources: str) -> object:
    return bootstrap.Inspection(state="unmanaged-existing", sources=tuple(sources))


def test_zero_primary_requires_creating_supported_instruction_file() -> None:
    inspection = migration_inspection("policy/core.md")

    assert bootstrap.available_primary_instructions(inspection) == ()
    assert bootstrap.select_primary_instructions(inspection, None, apply=False) is None

    guidance = bootstrap.primary_selection_guidance(())
    assert "Create one supported instruction file" in guidance
    assert "--primary-instructions" not in guidance

    with pytest.raises(ValueError, match="create one supported instruction file"):
        bootstrap.select_primary_instructions(inspection, None, apply=True)

    with pytest.raises(ValueError, match="available: none"):
        bootstrap.select_primary_instructions(inspection, "AGENTS.md", apply=False)


def test_single_primary_is_selected_automatically() -> None:
    inspection = migration_inspection("AGENTS.md")

    assert bootstrap.select_primary_instructions(inspection, None, apply=False) == "AGENTS.md"
    assert bootstrap.select_primary_instructions(inspection, None, apply=True) == "AGENTS.md"


def test_multiple_primaries_require_explicit_selection() -> None:
    inspection = migration_inspection("AGENTS.md", "CLAUDE.md")
    available = bootstrap.available_primary_instructions(inspection)

    assert available == ("AGENTS.md", "CLAUDE.md")
    assert bootstrap.select_primary_instructions(inspection, None, apply=False) is None

    guidance = bootstrap.primary_selection_guidance(available)
    assert "Multiple supported primary instruction files were discovered" in guidance
    assert "--primary-instructions <path>" in guidance

    with pytest.raises(ValueError, match="requires --primary-instructions"):
        bootstrap.select_primary_instructions(inspection, None, apply=True)

    assert (
        bootstrap.select_primary_instructions(inspection, "CLAUDE.md", apply=True)
        == "CLAUDE.md"
    )
