from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.run_policy_preflight import (
    TestPartition as PolicyTestPartition,
)
from scripts.run_policy_preflight import (
    _node_ids_digest,
    check_tests,
    classify_full_test_inventory,
    effective_full_test_jobs,
    effective_runner_jobs,
    run_pytest_subset,
    schedulable_full_test_module_count,
)


def _write_manifest(
    tmp_path: Path, module: str, node_ids: list[str], source: bytes
) -> tuple[Path, Path]:
    source_path = tmp_path / module
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(source)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "modules": {
                    module: {
                        "count": len(node_ids),
                        "node_ids_sha256": _node_ids_digest(node_ids),
                        "source_sha256": hashlib.sha256(source).hexdigest(),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return source_path, manifest_path


def test_full_partition_is_complete_disjoint_and_unknown_tests_are_serial(
    tmp_path: Path,
) -> None:
    parallel_ids = [
        "tests/test_config_driven_check.py::test_prepare",
        "tests/test_config_driven_check.py::test_validate",
    ]
    unknown_id = "tests/test_new_module.py::test_new"
    module = "tests/test_config_driven_check.py"
    _, manifest = _write_manifest(tmp_path, module, parallel_ids, b"reviewed source")

    partition = classify_full_test_inventory(
        [*parallel_ids, unknown_id], root=tmp_path, manifest_path=manifest
    )

    assert partition.parallel == tuple(sorted(parallel_ids))
    assert partition.serial == (unknown_id,)
    assert partition.exclusive == ()
    groups = [set(partition.parallel), set(partition.serial), set(partition.exclusive)]
    assert all(
        left.isdisjoint(right)
        for index, left in enumerate(groups)
        for right in groups[index + 1 :]
    )
    assert set.union(*groups) == set(partition.discovered)


def test_changed_or_added_test_in_reviewed_module_falls_back_to_serial(
    tmp_path: Path,
) -> None:
    module = "tests/test_config_driven_check.py"
    reviewed_ids = [f"{module}::test_prepare"]
    new_ids = [*reviewed_ids, f"{module}::test_new_case"]
    _, manifest = _write_manifest(tmp_path, module, reviewed_ids, b"old source")
    source_path = tmp_path / module
    source_path.write_bytes(b"new source")

    partition = classify_full_test_inventory(
        new_ids, root=tmp_path, manifest_path=manifest
    )

    assert partition.parallel == ()
    assert partition.serial == tuple(sorted(new_ids))
    assert partition.fallback_modules == (module,)


def test_canonical_worktree_test_is_exclusive(tmp_path: Path) -> None:
    module = "tests/test_maintainer_entrypoint_workflow.py"
    node_id = f"{module}::test_poisoning"
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"version": 1, "modules": {}}', encoding="utf-8")

    partition = classify_full_test_inventory(
        [node_id], root=tmp_path, manifest_path=manifest
    )

    assert partition.exclusive == (node_id,)
    assert partition.parallel == ()
    assert partition.serial == ()


def test_duplicate_and_empty_test_inventories_fail_closed(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"version": 1, "modules": {}}', encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        classify_full_test_inventory(
            ["tests/test_new.py::test_one"] * 2,
            root=tmp_path,
            manifest_path=manifest,
        )
    with pytest.raises(ValueError, match="empty"):
        classify_full_test_inventory([], root=tmp_path, manifest_path=manifest)


def test_subset_command_passes_only_explicit_worker_budget() -> None:
    node_ids = ["tests/test_a.py::test_one", "tests/test_a.py::test_two"]
    with patch("scripts.run_policy_preflight.subprocess.run") as child:
        run_pytest_subset("parallel", node_ids, requested_jobs=4, effective_jobs=2)

    command = child.call_args.args[0]
    assert command[command.index("-n") + 1] == "2"
    assert command[-2:] == node_ids
    assert child.call_args.kwargs["check"] is True


def test_subset_failure_propagates_to_parent() -> None:
    failure = subprocess.CalledProcessError(1, ["pytest"])
    with patch(
        "scripts.run_policy_preflight.subprocess.run", side_effect=failure
    ):
        with pytest.raises(subprocess.CalledProcessError):
            run_pytest_subset(
                "parallel", ["tests/test_a.py::test_one"], 2, 2
            )


def test_full_worker_count_is_bounded_and_jobs_one_is_serial() -> None:
    for requested in (1, 2, 4, 16):
        assert 1 <= effective_full_test_jobs(requested) <= requested
    assert effective_full_test_jobs(1) == 1
    assert effective_full_test_jobs(100, schedulable_modules=2) == 2


def test_jobs_one_runs_full_suite_without_partition_or_xdist() -> None:
    node_ids = ["tests/test_new.py::test_one"]
    calls: list[tuple[str, ...]] = []
    with (
        patch(
            "scripts.run_policy_preflight.collect_full_test_inventory",
            return_value=tuple(node_ids),
        ),
        patch("scripts.run_policy_preflight.run", side_effect=lambda *args: calls.append(args)),
    ):
        check_tests(jobs=1)

    assert len(calls) == 1
    assert calls[0][1:] == ("-m", "pytest", "-o", "addopts=-q")
    assert "-n" not in calls[0]


def test_parallel_full_suite_phases_respect_classification_barriers() -> None:
    partition = PolicyTestPartition(
        discovered=("parallel-1", "serial-1", "exclusive-1"),
        parallel=("parallel-1",),
        serial=("serial-1",),
        exclusive=("exclusive-1",),
        fallback_modules=(),
    )
    calls: list[tuple[str, tuple[str, ...], int, int]] = []
    with (
        patch(
            "scripts.run_policy_preflight.collect_full_test_inventory",
            return_value=partition.discovered,
        ),
        patch("scripts.run_policy_preflight.classify_full_test_inventory", return_value=partition),
        patch(
            "scripts.run_policy_preflight.run_pytest_subset",
            side_effect=lambda name, ids, requested, effective: calls.append(
                (name, tuple(ids), requested, effective)
            ),
        ),
    ):
        check_tests(jobs=2)

    assert calls == [
        ("parallel", ("parallel-1",), 2, 1),
        ("serial", ("serial-1",), 2, 1),
        ("exclusive", ("exclusive-1",), 2, 1),
    ]


def test_full_xdist_budget_is_capped_by_schedulable_modules() -> None:
    parallel = (
        "tests/test_alpha.py::test_one",
        "tests/test_alpha.py::test_two",
        "tests/test_beta.py::test_one",
        "tests/test_beta.py::test_two",
    )
    partition = PolicyTestPartition(
        discovered=parallel,
        parallel=parallel,
        serial=(),
        exclusive=(),
        fallback_modules=(),
    )
    calls: list[tuple[str, tuple[str, ...], int, int]] = []
    with (
        patch(
            "scripts.run_policy_preflight.collect_full_test_inventory",
            return_value=partition.discovered,
        ),
        patch("scripts.run_policy_preflight.classify_full_test_inventory", return_value=partition),
        patch(
            "scripts.run_policy_preflight.run_pytest_subset",
            side_effect=lambda name, ids, requested, effective: calls.append(
                (name, tuple(ids), requested, effective)
            ),
        ),
    ):
        check_tests(jobs=100)

    assert calls == [
        ("parallel", parallel, 100, 2),
        ("serial", (), 100, 2),
        ("exclusive", (), 100, 2),
    ]


def test_top_level_full_budget_uses_inventory_schedulable_modules() -> None:
    parallel = (
        "tests/test_alpha.py::test_one",
        "tests/test_alpha.py::test_two",
    )
    partition = PolicyTestPartition(
        discovered=parallel,
        parallel=parallel,
        serial=(),
        exclusive=(),
        fallback_modules=(),
    )
    with (
        patch("scripts.run_policy_preflight.collect_full_test_inventory", return_value=parallel),
        patch("scripts.run_policy_preflight.classify_full_test_inventory", return_value=partition),
    ):
        schedulable_modules = schedulable_full_test_module_count()

    assert schedulable_modules == 1
    assert effective_runner_jobs(
        "full", 100, schedulable_modules=schedulable_modules
    ) == 1
    assert effective_runner_jobs(
        "ready", 100, schedulable_modules=schedulable_modules
    ) == 1


def test_inventory_collector_clears_injected_pytest_worker_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import collect_policy_test_inventory as collector

    output = tmp_path / "node-ids.json"
    monkeypatch.setenv("PYTEST_ADDOPTS", "-n auto")

    def fake_pytest_main(_args: list[str], plugins: list[object]) -> pytest.ExitCode:
        assert "PYTEST_ADDOPTS" not in os.environ
        plugins[0].pytest_collection_finish(type("Session", (), {"items": []})())
        return pytest.ExitCode.OK

    with patch.object(collector.pytest, "main", side_effect=fake_pytest_main):
        assert collector.main(["--output", str(output)]) == 0

    assert json.loads(output.read_text(encoding="utf-8")) == []
