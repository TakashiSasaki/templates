from __future__ import annotations

import pytest

from agent_policy.config import package_root
from agent_policy.renderer import NON_GENERATED_SKILLS, render_skill


def test_agent_policy_runtime_skill_is_excluded_from_generated_skill_catalog() -> None:
    skill_name = "agent-policy"
    assert (package_root() / "skills" / skill_name).is_dir()
    assert skill_name in NON_GENERATED_SKILLS

    with pytest.raises(ValueError, match=f"Unknown generated skill: {skill_name}"):
        render_skill(skill_name)
