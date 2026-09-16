"""Executable counterexamples: green entrypoints need not execute claimed checks.

These miniature repositories exercise real pytest discovery and checker execution,
not a second Policy decision engine. Source/projection assertions bind their lesson
to the owning rule; runtime results establish only the fixtures' execution paths.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("route", "reachable"),
    [
        ("uncalled-helper", False),
        ("outside-discovery", False),
        ("uncalled-wrapper", False),
        ("unused-projection", False),
        ("optional-lane", False),
        ("required-helper", True),
    ],
)
def test_green_required_entrypoint_does_not_imply_claimed_execution(
    tmp_path: Path, route: str, reachable: bool,
) -> None:
    marker = tmp_path / "executed"
    (tmp_path / "helper.py").write_text(
        "from pathlib import Path\n"
        "def check():\n"
        "    Path('executed').write_text('claimed assertion reached')\n"
        "    assert 2 + 2 == 5, 'deliberately failing claimed assertion'\n",
        encoding="utf-8",
    )
    (tmp_path / "wrapper.py").write_text(
        "from helper import check\ndef main():\n    check()\n", encoding="utf-8",
    )
    (tmp_path / "generated_check.py").write_text(
        "from helper import check\ncheck()\n", encoding="utf-8",
    )
    (tmp_path / "regression.py").write_text(
        "from helper import check\ndef test_regression():\n    check()\n",
        encoding="utf-8",
    )
    entrypoints = {
        "uncalled-helper": "import helper\n",
        "uncalled-wrapper": "import wrapper\n",
        "unused-projection": "print('canonical checker uses another path')\n",
        "optional-lane": (
            "from helper import check\nif False:  # optional lane disabled\n    check()\n"
        ),
        "required-helper": "from wrapper import main\nmain()\n",
    }
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "PYTEST"))}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if route == "outside-discovery":
        (tmp_path / "pytest.ini").write_text("[pytest]\npython_files = test_*.py\n")
        (tmp_path / "test_unrelated.py").write_text("def test_other():\n    assert True\n")
        command = [sys.executable, "-m", "pytest", "-q"]
    else:
        (tmp_path / "required.py").write_text(entrypoints[route], encoding="utf-8")
        command = [sys.executable, "required.py"]
    result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert marker.exists() is reachable
    assert (result.returncode != 0) is reachable, result.stdout + result.stderr
    if reachable:
        assert "deliberately failing claimed assertion" in result.stderr
        # The required path detects the failure; repairing the assertion then
        # establishes execution plus success, not merely a static call edge.
        helper = tmp_path / "helper.py"
        helper.write_text(helper.read_text().replace("2 + 2 == 5", "2 + 2 == 4"))
        # Avoid timestamp/size-based bytecode reuse for the deliberate mutation.
        for cache in (tmp_path / "__pycache__").glob("helper.*.pyc"):
            cache.unlink()
        marker.unlink()
        repaired = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
        assert repaired.returncode == 0, repaired.stderr
        assert marker.exists()


def test_reachability_owner_and_rendered_procedure_remain_aligned() -> None:
    policy = (ROOT / "policy/core/testing.md").read_text()
    assert (
        "reachable from and actually executed by the authoritative validation entrypoint" in policy
    )
    assert "optional/non-required lane" in policy
    assert "Reachability alone is not a passing result" in policy
    assert "universal static call-graph tooling is not required" in policy
    rendered = render_skill("orchestrate-repository-change")
    stage = rendered["references/staged-ci-execution.md"]
    assert "testing.run-required-checks" in stage
    assert "static path or successful collection alone is not a passing assertion" in stage
    assert "report the coverage gap without claiming qualification" in stage
    assert "validation-reachability-self-audit" in rendered["SKILL.md"]
