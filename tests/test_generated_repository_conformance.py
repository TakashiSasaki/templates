from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

ROOT = Path(__file__).resolve().parents[1]
DISTRIBUTION_ROOT = ROOT / "template"

PRODUCT_NAME = "Conformance Workbench"
PROOF_COMMAND_ID = "generated-product-proof"
RELEASE_GATE_ID = "generated-product-release"
PROOF_COMMAND = "python product/prove_conformance.py"

_PYTHON_ENVIRONMENT_INPUTS = (
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONSAFEPATH",
    "PYTHONPLATLIBDIR",
    "PYTHONHASHSEED",
    "PYTHONUTF8",
    "PYTHONINTMAXSTRDIGITS",
    "PYTHONMALLOC",
    "PYTHONIOENCODING",
    "PYTHONTRACEMALLOC",
    "PYTHONINSPECT",
)

PRODUCT_PROOF_SCRIPT = r'''#!/usr/bin/env python3
"""Execute the reviewed proof command for the generated-repository fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_NAME = "Conformance Workbench"
COMMAND_ID = "generated-product-proof"
GATE_ID = "generated-product-release"
COMMAND = "python product/prove_conformance.py"


def load_json(relative: str) -> object:
    with (ROOT / relative).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fail(message: str) -> None:
    print(f"generated repository proof failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    surfaces = load_json("contracts/surfaces.json")
    routes = load_json("contracts/routes.json")
    states = load_json("contracts/ui-states.json")
    viewports = load_json("contracts/viewports.json")
    evidence = load_json("contracts/implementation-evidence.json")
    inventory = load_json("product/conformance-targets.json")

    expected_surface_titles = {
        "public": f"{PRODUCT_NAME} public surface",
        "application": f"{PRODUCT_NAME} workspace",
        "status": f"{PRODUCT_NAME} service status",
    }
    actual_surface_titles = {
        surface["id"]: surface["title"] for surface in surfaces["surfaces"]
    }
    if actual_surface_titles != expected_surface_titles:
        fail("surface declarations are not the reviewed product values")

    expected_route_paths = {
        "home": "/",
        "application-home": "/workspace",
        "status": "/health",
    }
    actual_route_paths = {route["id"]: route["path"] for route in routes["routes"]}
    if actual_route_paths != expected_route_paths:
        fail("route declarations are not the reviewed product values")

    state_prefix = f"{PRODUCT_NAME} product state: "
    if any(
        not state["description"].startswith(state_prefix)
        for state in states["states"]
    ):
        fail("UI-state declarations retain template example descriptions")

    viewport_prefix = f"{PRODUCT_NAME} product viewport: "
    if any(
        not viewport["description"].startswith(viewport_prefix)
        for viewport in viewports["viewports"]
    ):
        fail("viewport declarations retain template example descriptions")

    if evidence["mode"] != "product":
        fail("implementation evidence is not in product mode")
    if evidence["commands"] != [
        {
            "id": COMMAND_ID,
            "command": COMMAND,
            "purpose": "Run every reviewed generated-product proof.",
        }
    ]:
        fail("authoritative proof command registration changed")
    if evidence["releaseGates"] != [
        {
            "id": GATE_ID,
            "purpose": "Block fixture release unless all generated-product proofs pass.",
            "commandIds": [COMMAND_ID],
        }
    ]:
        fail("selected release gate registration changed")

    targets = inventory.get("targets")
    if inventory.get("product") != PRODUCT_NAME or not isinstance(targets, dict):
        fail("product target inventory is malformed")

    record_ids = {record["id"] for record in evidence["records"]}
    if set(targets) != record_ids:
        fail("product target inventory does not match the evidence target set")

    proof_count = 0
    for record in evidence["records"]:
        record_id = record["id"]
        target = targets[record_id]
        boundary_locator = (
            f"product/conformance-targets.json#/targets/{record_id}/implementation"
        )
        if record["implementationBoundary"] != {
            "status": "verified",
            "description": record["implementationBoundary"]["description"],
            "locator": boundary_locator,
        }:
            fail(f"{record_id}: implementation boundary is not the reviewed locator")
        if record["releaseGateIds"] != [GATE_ID]:
            fail(f"{record_id}: selected release gate changed")
        if not isinstance(target.get("implementation"), str) or not target["implementation"]:
            fail(f"{record_id}: implementation inventory entry is empty")

        for polarity, field in (
            ("positive", "positiveEvidence"),
            ("negative", "negativeEvidence"),
        ):
            proofs = record[field]
            if len(proofs) != 1:
                fail(f"{record_id}: expected exactly one {polarity} proof")
            proof = proofs[0]
            expected_locator = (
                f"product/conformance-targets.json#/targets/{record_id}/{polarity}"
            )
            if proof.get("status") != "verified":
                fail(f"{record_id}: {polarity} proof is not verified")
            if proof.get("kind") != "integration-test":
                fail(f"{record_id}: {polarity} proof kind changed")
            if proof.get("locator") != expected_locator:
                fail(f"{record_id}: {polarity} proof locator changed")
            if proof.get("commandId") != COMMAND_ID:
                fail(f"{record_id}: {polarity} proof command changed")
            if not isinstance(proof.get("expectedResult"), str) or not proof["expectedResult"]:
                fail(f"{record_id}: {polarity} expected result is empty")
            if target.get(polarity) is not True:
                fail(f"{record_id}: {polarity} proof result is not true")
            proof_count += 1

    print(f"generated repository proof: {proof_count} checks passed")


if __name__ == "__main__":
    main()
'''


def _load_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored = {".git", ".venv", ".pytest_cache", "__pycache__"}
    return {name for name in names if name in ignored or name.endswith(".pyc")}


def _generated_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in _PYTHON_ENVIRONMENT_INPUTS:
        environment[name] = ""
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def _run_generated_python(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=root,
        env=_generated_environment(),
        check=False,
        capture_output=True,
        text=True,
    )


def _settle_product_contracts(root: Path) -> None:
    surfaces_path = root / "contracts/surfaces.json"
    surfaces = _load_json(surfaces_path)
    surface_values = {
        "public": (
            f"{PRODUCT_NAME} public surface",
            "Publish product information approved for anonymous access.",
        ),
        "application": (
            f"{PRODUCT_NAME} workspace",
            "Provide the reviewed workspace workflow to authorized product users.",
        ),
        "status": (
            f"{PRODUCT_NAME} service status",
            "Publish sanitized health information for the generated product.",
        ),
    }
    for surface in surfaces["surfaces"]:
        surface["title"], surface["purpose"] = surface_values[surface["id"]]
    _write_json(surfaces_path, surfaces)

    routes_path = root / "contracts/routes.json"
    routes = _load_json(routes_path)
    route_paths = {
        "home": "/",
        "application-home": "/workspace",
        "status": "/health",
    }
    for route in routes["routes"]:
        route["path"] = route_paths[route["id"]]
    _write_json(routes_path, routes)

    states_path = root / "contracts/ui-states.json"
    states = _load_json(states_path)
    for state in states["states"]:
        state["description"] = (
            f"{PRODUCT_NAME} product state: {state['description']}"
        )
    _write_json(states_path, states)

    viewports_path = root / "contracts/viewports.json"
    viewports = _load_json(viewports_path)
    for viewport in viewports["viewports"]:
        viewport["description"] = (
            f"{PRODUCT_NAME} product viewport: {viewport['description']}"
        )
    _write_json(viewports_path, viewports)


def _materialize_product_evidence(root: Path) -> None:
    evidence_path = root / "contracts/implementation-evidence.json"
    evidence = _load_json(evidence_path)
    evidence["mode"] = "product"
    evidence["commands"] = [
        {
            "id": PROOF_COMMAND_ID,
            "command": PROOF_COMMAND,
            "purpose": "Run every reviewed generated-product proof.",
        }
    ]
    evidence["releaseGates"] = [
        {
            "id": RELEASE_GATE_ID,
            "purpose": "Block fixture release unless all generated-product proofs pass.",
            "commandIds": [PROOF_COMMAND_ID],
        }
    ]

    inventory: dict[str, object] = {
        "product": PRODUCT_NAME,
        "targets": {},
    }
    targets = inventory["targets"]
    assert isinstance(targets, dict)

    for record in evidence["records"]:
        record_id = record["id"]
        record["implementationBoundary"]["status"] = "verified"
        record["implementationBoundary"]["locator"] = (
            f"product/conformance-targets.json#/targets/{record_id}/implementation"
        )
        record["releaseGateIds"] = [RELEASE_GATE_ID]
        targets[record_id] = {
            "implementation": f"Reviewed implementation boundary for {record_id}.",
            "positive": True,
            "negative": True,
        }
        for polarity, field in (
            ("positive", "positiveEvidence"),
            ("negative", "negativeEvidence"),
        ):
            for proof in record[field]:
                proof.update(
                    {
                        "status": "verified",
                        "kind": "integration-test",
                        "locator": (
                            "product/conformance-targets.json#/targets/"
                            f"{record_id}/{polarity}"
                        ),
                        "commandId": PROOF_COMMAND_ID,
                        "expectedResult": (
                            f"The reviewed {polarity} behavior for {record_id} is observed."
                        ),
                    }
                )

    _write_json(evidence_path, evidence)
    product = root / "product"
    product.mkdir()
    _write_json(product / "conformance-targets.json", inventory)
    proof_script = product / "prove_conformance.py"
    proof_script.write_text(PRODUCT_PROOF_SCRIPT, encoding="utf-8")
    proof_script.chmod(0o755)


@contextmanager
def _generated_repository() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory) / "generated-repository"
        shutil.copytree(DISTRIBUTION_ROOT, root, ignore=_copy_ignore)
        _settle_product_contracts(root)
        _materialize_product_evidence(root)
        yield root


def _mutate_evidence(
    root: Path,
    mutation: Callable[[dict[str, object]], None],
) -> None:
    evidence_path = root / "contracts/implementation-evidence.json"
    evidence = _load_json(evidence_path)
    mutation(evidence)
    _write_json(evidence_path, evidence)


def _is_template_maintainer_source() -> bool:
    evidence = _load_json(ROOT / "contracts/implementation-evidence.json")
    return evidence.get("mode") == "template"


@unittest.skipUnless(
    _is_template_maintainer_source(),
    "template-maintainer-only generated-repository conformance suite",
)
class GeneratedRepositoryConformanceTests(unittest.TestCase):
    def assert_generated_validator_rejects(
        self,
        root: Path,
        diagnostic: str,
    ) -> None:
        result = _run_generated_python(
            root,
            "scripts/validate_implementation_evidence.py",
        )
        self.assertEqual(
            1,
            result.returncode,
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn(diagnostic, result.stderr)

    def test_clean_room_generated_repository_is_product_conformant(self) -> None:
        source_evidence = _load_json(ROOT / "contracts/implementation-evidence.json")
        distributed_evidence = _load_json(
            DISTRIBUTION_ROOT / "contracts/implementation-evidence.json"
        )
        self.assertEqual("template", source_evidence["mode"])
        self.assertEqual("template", distributed_evidence["mode"])

        with _generated_repository() as root:
            self.assertFalse((root / ".git").exists())
            self.assertFalse((root / "template").exists())
            self.assertFalse((root / "distribution-manifest.json").exists())
            self.assertFalse((root / "docs/publication-catalog.json").exists())
            self.assertFalse((root / "scripts/validate_distribution.py").exists())
            self.assertFalse(
                (root / "scripts/validate_publication_catalog.py").exists()
            )
            self.assertEqual(
                "product",
                _load_json(root / "contracts/implementation-evidence.json")["mode"],
            )

            proof = _run_generated_python(root, "product/prove_conformance.py")
            self.assertEqual(0, proof.returncode, proof.stderr)
            self.assertIn("generated repository proof: 52 checks passed", proof.stdout)

            validator_commands = (
                ("scripts/validate_contracts.py",),
                ("-m", "scripts.validate_contracts"),
                ("scripts/validate_contract_evolution.py",),
                ("-m", "scripts.validate_contract_evolution"),
                ("scripts/validate_implementation_evidence.py",),
                ("-m", "scripts.validate_implementation_evidence"),
            )
            for command in validator_commands:
                with self.subTest(command=command):
                    result = _run_generated_python(root, *command)
                    self.assertEqual(
                        0,
                        result.returncode,
                        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                    )

        self.assertEqual(
            "template",
            _load_json(ROOT / "contracts/implementation-evidence.json")["mode"],
        )
        self.assertEqual(
            "template",
            _load_json(
                DISTRIBUTION_ROOT / "contracts/implementation-evidence.json"
            )["mode"],
        )
        self.assertFalse((ROOT / "product").exists())
        self.assertFalse((DISTRIBUTION_ROOT / "product").exists())

    def test_template_mode_residue_is_rejected_by_copied_validator(self) -> None:
        with _generated_repository() as root:
            _mutate_evidence(root, lambda evidence: evidence.__setitem__("mode", "template"))
            self.assert_generated_validator_rejects(
                root,
                "implementation evidence: template mode requires commands to be empty",
            )

    def test_missing_target_is_rejected_by_copied_validator(self) -> None:
        with _generated_repository() as root:
            def remove_target(evidence: dict[str, object]) -> None:
                evidence["records"] = [
                    record
                    for record in evidence["records"]
                    if record["target"] != {"kind": "surface", "id": "public"}
                ]

            _mutate_evidence(root, remove_target)
            self.assert_generated_validator_rejects(
                root,
                "missing implementation evidence target: surface public",
            )

    def test_unverified_boundary_is_rejected_by_copied_validator(self) -> None:
        with _generated_repository() as root:
            def unverify_boundary(evidence: dict[str, object]) -> None:
                evidence["records"][0]["implementationBoundary"]["status"] = "required"

            _mutate_evidence(root, unverify_boundary)
            self.assert_generated_validator_rejects(
                root,
                "implementation evidence record surface-public: product mode requires a verified implementation boundary",
            )

    def test_unknown_command_is_rejected_by_copied_validator(self) -> None:
        with _generated_repository() as root:
            def select_unknown_command(evidence: dict[str, object]) -> None:
                evidence["records"][0]["positiveEvidence"][0]["commandId"] = "unknown-command"

            _mutate_evidence(root, select_unknown_command)
            self.assert_generated_validator_rejects(
                root,
                "implementation evidence record surface-public proof surface-public-positive: unknown command reference unknown-command",
            )

    def test_unused_command_is_rejected_by_copied_validator(self) -> None:
        with _generated_repository() as root:
            def add_unused_command(evidence: dict[str, object]) -> None:
                evidence["commands"].append(
                    {
                        "id": "unused-command",
                        "command": "python product/unused.py",
                        "purpose": "Deliberately unused command for the negative fixture.",
                    }
                )

            _mutate_evidence(root, add_unused_command)
            self.assert_generated_validator_rejects(
                root,
                "unused implementation evidence command: unused-command",
            )

    def test_unused_release_gate_is_rejected_by_copied_validator(self) -> None:
        with _generated_repository() as root:
            def add_unused_gate(evidence: dict[str, object]) -> None:
                evidence["releaseGates"].append(
                    {
                        "id": "unused-gate",
                        "purpose": "Deliberately unused gate for the negative fixture.",
                        "commandIds": [PROOF_COMMAND_ID],
                    }
                )

            _mutate_evidence(root, add_unused_gate)
            self.assert_generated_validator_rejects(
                root,
                "unused implementation evidence release gate: unused-gate",
            )

    def test_release_gate_closure_is_rejected_by_copied_validator(self) -> None:
        with _generated_repository() as root:
            def break_release_gate_closure(evidence: dict[str, object]) -> None:
                evidence["commands"].append(
                    {
                        "id": "detached-proof",
                        "command": "python product/detached.py",
                        "purpose": "Exercise one proof outside the selected release gate.",
                    }
                )
                evidence["records"][0]["positiveEvidence"][0]["commandId"] = "detached-proof"

            _mutate_evidence(root, break_release_gate_closure)
            self.assert_generated_validator_rejects(
                root,
                "implementation evidence record surface-public: evidence command detached-proof is not executed by a selected release gate",
            )

    def test_reviewed_proof_command_rejects_false_result(self) -> None:
        with _generated_repository() as root:
            inventory_path = root / "product/conformance-targets.json"
            inventory = _load_json(inventory_path)
            inventory["targets"]["surface-public"]["negative"] = False
            _write_json(inventory_path, inventory)

            result = _run_generated_python(root, "product/prove_conformance.py")

        self.assertEqual(1, result.returncode)
        self.assertIn(
            "generated repository proof failed: surface-public: negative proof result is not true",
            result.stderr,
        )


class GeneratedRepositoryConformanceScopeTests(unittest.TestCase):
    def test_clean_room_suite_is_template_maintainer_only(self) -> None:
        source_is_template = _is_template_maintainer_source()
        suite_is_skipped = bool(
            getattr(GeneratedRepositoryConformanceTests, "__unittest_skip__", False)
        )
        self.assertEqual(not source_is_template, suite_is_skipped)
        if suite_is_skipped:
            self.assertEqual(
                "template-maintainer-only generated-repository conformance suite",
                getattr(GeneratedRepositoryConformanceTests, "__unittest_skip_why__"),
            )

    def test_shared_fixture_source_is_the_copyable_distribution(self) -> None:
        self.assertTrue(DISTRIBUTION_ROOT.is_dir())
        self.assertTrue((DISTRIBUTION_ROOT / "README.md").is_file())
        self.assertTrue((DISTRIBUTION_ROOT / "contracts/manifest.json").is_file())
        self.assertFalse((DISTRIBUTION_ROOT / "distribution-manifest.json").exists())
        self.assertFalse(
            (DISTRIBUTION_ROOT / "docs/publication-catalog.json").exists()
        )


if __name__ == "__main__":
    unittest.main()
