from __future__ import annotations

import importlib.util
import inspect
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "matched_policy_delivery_experiment",
    ROOT / "scripts/run_matched_policy_delivery_experiment.py",
)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_skill_provenance_uses_candidate_provider_root(tmp_path: Path) -> None:
    provider = tmp_path / "provider"
    experiment_runner = tmp_path / "runner"
    candidate_skill = provider / "skills/agent-policy/scripts"
    runner_skill = experiment_runner / "skills/agent-policy/scripts"
    candidate_skill.mkdir(parents=True)
    runner_skill.mkdir(parents=True)
    (candidate_skill / "run.py").write_text("candidate bytes\n", encoding="utf-8")
    (runner_skill / "run.py").write_text("untrusted runner bytes\n", encoding="utf-8")

    source_root, manifest = runner.resolve_candidate_skill(provider)

    assert source_root == provider / "skills/agent-policy"
    assert manifest["file_sha256"]["scripts/run.py"] == runner.sha(
        b"candidate bytes\n"
    )
    assert manifest["file_sha256"]["scripts/run.py"] != runner.sha(
        b"untrusted runner bytes\n"
    )
    source = inspect.getsource(runner.render_consumer)
    assert "resolve_candidate_skill(provider_root)" in source
    assert "Path(__file__).parents[1] / \"skills/agent-policy\"" not in source


def test_provider_binding_rejects_a_different_revision(tmp_path: Path) -> None:
    provider = tmp_path / "provider"
    skill = provider / "skills/agent-policy"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("candidate\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=provider, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=provider,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Policy test"], cwd=provider, check=True
    )
    subprocess.run(["git", "add", "."], cwd=provider, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "candidate"], cwd=provider, check=True
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=provider,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert runner.verify_provider_root(provider, head)["revision"] == head
    try:
        runner.verify_provider_root(provider, "0" * 40)
    except RuntimeError as exc:
        assert "revision mismatch" in str(exc)
    else:
        raise AssertionError("provider revision mismatch was accepted")


def test_code_repair_grader_requires_behavior_and_real_regression(
    tmp_path: Path,
) -> None:
    runner.setup_task(tmp_path, "code-repair")
    comment_only = (tmp_path / "tests/test_calculator.py").read_text(encoding="utf-8")
    (tmp_path / "tests/test_calculator.py").write_text(
        comment_only + "\n# average([1, 3, 5]) == 3.0\n", encoding="utf-8"
    )
    failed = runner.grade("code-repair", tmp_path, [])
    assert not failed["passed"]
    assert failed["implementation_contains_defect"]

    (tmp_path / "src/calculator.py").write_text(
        "def average(values: list[float]) -> float:\n"
        "    return sum(values) / len(values)\n",
        encoding="utf-8",
    )
    (tmp_path / "tests/test_calculator.py").write_text(
        "from __future__ import annotations\n"
        "import sys\nimport unittest\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))\n"
        "from calculator import average\n"
        "class AverageTests(unittest.TestCase):\n"
        "    def test_average_three_values(self) -> None:\n"
        "        self.assertEqual(average([1, 3, 5]), 3.0)\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    passed = runner.grade("code-repair", tmp_path, [])
    assert passed["passed"]
    assert not passed["implementation_contains_defect"]
    assert passed["behavior_exit_code"] == 0


def test_review_preparation_grader_requires_all_operational_fields(
    tmp_path: Path,
) -> None:
    runner.setup_task(tmp_path, "review-preparation")
    (tmp_path / "review-preparation.txt").write_text(
        "repository=fixture/review-preparation\n"
        "pull_request=42\n"
        f"head={runner.REVIEW_HEAD}\n"
        f"base={runner.REVIEW_BASE}\n"
        f"effective_base={runner.REVIEW_EFFECTIVE_BASE}\n"
        "ci_state=success\n"
        f"ci_head={runner.REVIEW_HEAD}\n"
        "review_state=completed\n"
        f"review_head={runner.REVIEW_HEAD}\n"
        "next_safe_action=run local final review\n",
        encoding="utf-8",
    )
    passed = runner.grade("review-preparation", tmp_path, [])
    assert passed["passed"]

    (tmp_path / "review-preparation.txt").write_text(
        "repository=fixture/review-preparation\n"
        "pull_request=42\n"
        f"head={runner.REVIEW_HEAD}\n"
        f"base={runner.REVIEW_BASE}\n"
        f"effective_base={runner.REVIEW_EFFECTIVE_BASE}\n",
        encoding="utf-8",
    )
    incomplete = runner.grade("review-preparation", tmp_path, [])
    assert not incomplete["passed"]


def test_bootstrap_failure_is_bounded_and_redacted() -> None:
    stderr = (
        "Reading additional input from stdin...\n"
        "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n"
    )
    evidence = runner.bootstrap_evidence(stderr, 0, False, [], [])
    assert evidence["classification"] == "bootstrap_failure"
    assert evidence["normalized_reason"] == (
        "sandbox_bootstrap_network_namespace_unavailable"
    )
    assert evidence["reached_tool_boundary"] is False
    assert evidence["stderr_sha256"] == runner.sha(stderr.encode())
    assert evidence["stderr_bytes"] == len(stderr.encode())
