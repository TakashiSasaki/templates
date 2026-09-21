from __future__ import annotations

import importlib.util
import inspect
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "matched_policy_delivery_experiment",
    ROOT / "scripts/run_matched_policy_delivery_experiment.py",
)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def _candidate_repository(root: Path, *, marker: str = "candidate") -> tuple[Path, str]:
    provider = root / marker
    (provider / "src/agent_policy").mkdir(parents=True)
    (provider / "src/agent_policy/__init__.py").write_text(
        f"MARKER = {marker!r}\n", encoding="utf-8"
    )
    for directory in ("schemas", "profiles", "policy", "templates", "skills", "delivery"):
        path = provider / directory
        path.mkdir(parents=True)
        (path / "marker.txt").write_text(f"{marker}:{directory}\n", encoding="utf-8")
    skill_dir = provider / "skills/agent-policy"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        f"# {marker}\n", encoding="utf-8"
    )
    (provider / "requirements-runtime.lock").write_text(
        "Jinja2===3.1.6\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q"], cwd=provider, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=provider,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Policy test"], cwd=provider, check=True)
    subprocess.run(["git", "add", "."], cwd=provider, check=True)
    subprocess.run(["git", "commit", "-qm", marker], cwd=provider, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=provider, capture_output=True, text=True, check=True
    ).stdout.strip()
    return provider, head


def _candidate_wheel(path: Path, provider: Path) -> Path:
    wheel = path / f"{provider.name}.whl"
    manifest = runner.candidate_package_manifest(provider)
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in manifest:
            if name.startswith("agent_policy/_data/"):
                source = provider / name.removeprefix("agent_policy/_data/")
            else:
                source = provider / "src" / name
            archive.writestr(name, source.read_bytes())
        archive.writestr(
            "candidate-0.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: candidate\nVersion: 0.0\n",
        )
    return wheel


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


def test_wheel_and_runtime_lock_are_bound_to_provider_candidate(tmp_path: Path) -> None:
    provider, head = _candidate_repository(tmp_path, marker="candidate")
    wheel = _candidate_wheel(tmp_path, provider)
    binding = runner.verify_provider_root(provider, head)
    valid = runner.verify_wheel_candidate(
        wheel, provider, provider / "requirements-runtime.lock", binding
    )
    assert valid["candidate_revision"] == head
    assert valid["payload_files"] == runner.candidate_package_manifest(provider)

    old_provider, old_head = _candidate_repository(tmp_path, marker="old")
    old_wheel = _candidate_wheel(tmp_path, old_provider)
    assert runner.verify_provider_root(old_provider, old_head)["revision"] == old_head
    try:
        runner.verify_wheel_candidate(
            old_wheel, provider, provider / "requirements-runtime.lock", binding
        )
    except RuntimeError as exc:
        assert "payload mismatch" in str(exc)
    else:
        raise AssertionError("wheel from a different candidate was accepted")

    wrong_lock = tmp_path / "wrong-runtime.lock"
    wrong_lock.write_text("Jinja2===0.0.0\n", encoding="utf-8")
    try:
        runner.verify_wheel_candidate(wheel, provider, wrong_lock, binding)
    except RuntimeError as exc:
        assert "runtime requirements" in str(exc)
    else:
        raise AssertionError("runtime lock from a different candidate was accepted")


def test_wheel_candidate_rejects_extra_or_changed_payload(tmp_path: Path) -> None:
    provider, head = _candidate_repository(tmp_path)
    binding = runner.verify_provider_root(provider, head)
    wheel = _candidate_wheel(tmp_path, provider)
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("agent_policy/extra.py", "unrelated\n")
    try:
        runner.verify_wheel_candidate(
            wheel, provider, provider / "requirements-runtime.lock", binding
        )
    except RuntimeError as exc:
        assert "payload mismatch" in str(exc)
    else:
        raise AssertionError("extra wheel payload was accepted")


def test_generator_grader_requires_observed_canonical_workflow(tmp_path: Path) -> None:
    runner.setup_task(tmp_path, "generated-artifact")
    source = json.loads((tmp_path / "source/catalog.json").read_text())
    source["items"].append("gamma")
    (tmp_path / "source/catalog.json").write_text(json.dumps(source) + "\n")
    environment = dict(runner.os.environ)
    environment["POLICY_EXPERIMENT_TRACE"] = str(tmp_path / ".experiment-trace")
    subprocess.run(
        [runner.sys.executable, "scripts/generate_catalog.py"],
        cwd=tmp_path,
        env=environment,
        check=True,
    )
    commands = [{
        "command": "python scripts/generate_catalog.py",
        "exit_code": 0,
        "output": "",
        "output_bytes": 0,
    }]
    assert runner.grade("generated-artifact", tmp_path, commands)["passed"]

    (tmp_path / ".experiment-trace").write_text("", encoding="utf-8")
    assert not runner.grade("generated-artifact", tmp_path, commands)["passed"]
    (tmp_path / ".experiment-trace").write_text("generate_catalog.py\n", encoding="utf-8")
    assert not runner.grade(
        "generated-artifact", tmp_path,
        [{**commands[0], "command": "echo scripts/generate_catalog.py"}],
    )["passed"]
    assert not runner.grade(
        "generated-artifact", tmp_path,
        [{**commands[0], "command": "python scripts/not-the-generator.py"}],
    )["passed"]


def test_generator_grader_rejects_correct_output_without_generator_event(tmp_path: Path) -> None:
    runner.setup_task(tmp_path, "generated-artifact")
    (tmp_path / "source/catalog.json").write_text(
        '{"items": ["alpha", "beta", "gamma"]}\n', encoding="utf-8"
    )
    (tmp_path / "generated/catalog.json").write_text(
        '{"generated_by": "scripts/generate_catalog.py", '
        '"items": ["alpha", "beta", "gamma"]}\n', encoding="utf-8"
    )
    (tmp_path / ".experiment-trace").write_text("generate_catalog.py\n", encoding="utf-8")
    assert not runner.grade("generated-artifact", tmp_path, [])["passed"]


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
        (tmp_path / "review-preparation.txt").read_text(encoding="utf-8").replace(
            runner.REVIEW_HEAD, "4" * 40, 1
        ),
        encoding="utf-8",
    )
    assert not runner.grade("review-preparation", tmp_path, [])["passed"]

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
