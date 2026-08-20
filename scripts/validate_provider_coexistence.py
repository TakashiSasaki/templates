#!/usr/bin/env python3
"""Validate Policy/Composition coexistence using exact provider checkouts.

This is a Site-owned integration harness. It creates only temporary consumer
repositories, invokes each provider through its public command surface, and
observes cross-authority invariants. It does not parse or mutate provider
metadata as a management authority.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

POLICY_STATE_ROOTS = (
    ".agent-policy.yml",
    ".agent-policy.lock",
    ".agent-policy",
)
COMPOSITION_STATE_ROOTS = (".template-composition",)


class IntegrationError(RuntimeError):
    pass


def _run(
    arguments: list[str],
    *,
    cwd: Path | None = None,
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        arguments,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != expected:
        raise IntegrationError(
            "command returned an unexpected status\n"
            f"command={arguments!r}\n"
            f"expected={expected} actual={result.returncode}\n"
            f"stdout={result.stdout}\n"
            f"stderr={result.stderr}"
        )
    return result


def _json_stdout(result: subprocess.CompletedProcess[str], *, label: str) -> Any:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise IntegrationError(
            f"{label} did not emit JSON: {exc}; stdout={result.stdout!r}"
        ) from exc


def _head(root: Path) -> str:
    return _run(["git", "-C", str(root), "rev-parse", "HEAD"]).stdout.strip()


def _assert_exact_revision(root: Path, expected: str, *, provider: str) -> None:
    actual = _head(root)
    if actual != expected:
        raise IntegrationError(
            f"{provider} checkout is not the locked revision: expected {expected}, found {actual}"
        )


def _init_repository(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)
    _run(["git", "init", "--quiet", "--initial-branch=main", str(path)])


def _snapshot_entry(
    root: Path,
    path: Path,
    relative: str,
    result: dict[str, tuple[str, bytes]],
) -> None:
    if path.is_symlink():
        result[relative] = ("symlink", os.readlink(path).encode("utf-8"))
        return
    if path.is_file():
        result[relative] = ("file", path.read_bytes())
        return
    if path.is_dir():
        result[relative] = ("directory", b"")
        for child in sorted(path.iterdir(), key=lambda item: item.name):
            child_relative = f"{relative}/{child.name}" if relative else child.name
            _snapshot_entry(root, child, child_relative, result)
        return
    if path.exists():
        result[relative] = ("other", b"")


def _snapshot(root: Path, names: tuple[str, ...]) -> dict[str, tuple[str, bytes]]:
    result: dict[str, tuple[str, bytes]] = {}
    for name in names:
        path = root / name
        if path.exists() or path.is_symlink():
            _snapshot_entry(root, path, name, result)
    return result


def _assert_snapshot_unchanged(
    root: Path,
    names: tuple[str, ...],
    expected: dict[str, tuple[str, bytes]],
    *,
    label: str,
) -> None:
    actual = _snapshot(root, names)
    if actual != expected:
        before = sorted(expected)
        after = sorted(actual)
        raise IntegrationError(
            f"{label} changed unexpectedly; before={before}, after={after}"
        )


def _assert_absent(root: Path, names: tuple[str, ...], *, label: str) -> None:
    present = [name for name in names if (root / name).exists() or (root / name).is_symlink()]
    if present:
        raise IntegrationError(f"{label} unexpectedly exists: {present}")


def _write_composition_config(path: Path, recipe: str) -> None:
    value = {
        "schema_version": 1,
        "recipe": recipe,
        "components": {"include": [], "exclude": []},
        "parameters": {},
    }
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _absolute_without_resolving(path: Path) -> Path:
    """Return an absolute path while preserving an executable symlink identity."""
    return Path(os.path.abspath(path))


class Harness:
    def __init__(
        self,
        *,
        composition_root: Path,
        composition_python: Path,
        composition_revision: str,
        policy_root: Path,
        policy_cli: Path,
        policy_revision: str,
    ) -> None:
        self.composition_root = composition_root.resolve()
        self.composition_python = _absolute_without_resolving(composition_python)
        self.composition_revision = composition_revision
        self.policy_root = policy_root.resolve()
        self.policy_cli = _absolute_without_resolving(policy_cli)
        self.policy_revision = policy_revision
        self.composer = self.composition_root / "scripts" / "compose.py"

    def verify_inputs(self) -> None:
        for path, label in (
            (self.composer, "Composer entrypoint"),
            (self.composition_python, "Composition Python"),
            (self.policy_cli, "Policy CLI"),
        ):
            if not path.is_file():
                raise IntegrationError(f"{label} is unavailable: {path}")
        _assert_exact_revision(
            self.composition_root,
            self.composition_revision,
            provider="composition",
        )
        _assert_exact_revision(
            self.policy_root,
            self.policy_revision,
            provider="policy",
        )

    def composition(
        self,
        command: str,
        *,
        target: Path,
        config: Path | None = None,
        mode: str | None = None,
        expected: int = 0,
    ) -> Any:
        arguments = [str(self.composition_python), str(self.composer), command]
        if mode is not None:
            arguments.extend(["--mode", mode])
        if config is not None:
            arguments.extend(["--config", str(config)])
        arguments.extend(["--target", str(target)])
        result = _run(arguments, cwd=self.composition_root, expected=expected)
        return _json_stdout(result, label=f"Composer {command}")

    def policy(
        self,
        target: Path,
        *arguments: str,
        expected: int = 0,
    ) -> Any:
        result = _run(
            [
                str(self.policy_cli),
                "--repository",
                str(target),
                "--format",
                "json",
                *arguments,
            ],
            cwd=self.policy_root,
            expected=expected,
        )
        return _json_stdout(result, label=f"agent-policy {' '.join(arguments)}")

    def adopt_policy_fresh(self, target: Path) -> None:
        self.policy(
            target,
            "adopt",
            "prepare",
            "--toolchain-revision",
            self.policy_revision,
            "--no-verification",
            "--no-skills",
            "--apply",
        )
        self.policy(target, "validate")

    def adopt_policy_migration(self, target: Path) -> None:
        self.policy(
            target,
            "adopt",
            "prepare",
            "--toolchain-revision",
            self.policy_revision,
            "--primary-instructions",
            "AGENTS.md",
            "--no-verification",
            "--no-skills",
            "--apply",
        )
        self.policy(target, "adopt", "preview")
        self.policy(target, "adopt", "finalize", "--apply")
        self.policy(target, "validate")

    def policy_only(self, root: Path) -> None:
        target = root / "policy-only"
        _init_repository(target)
        self.adopt_policy_fresh(target)
        if not (target / ".agent-policy.lock").is_file():
            raise IntegrationError("Policy-only fixture did not create .agent-policy.lock")
        _assert_absent(
            target,
            COMPOSITION_STATE_ROOTS,
            label="Composition state in Policy-only fixture",
        )

    def composition_only(self, root: Path) -> None:
        target = root / "composition-only"
        _init_repository(target)
        config = root / "composition-only.json"
        _write_composition_config(config, "webapp")
        payload = self.composition("apply", target=target, config=config)
        if payload.get("status") != "applied":
            raise IntegrationError(f"unexpected Composition apply payload: {payload}")
        validation = self.composition("validate", target=target)
        if validation.get("status") != "valid":
            raise IntegrationError(f"Composition-only fixture is not valid: {validation}")
        _assert_absent(
            target,
            POLICY_STATE_ROOTS,
            label="Policy state in Composition-only fixture",
        )

    def dual_authority(self, root: Path) -> None:
        target = root / "dual"
        _init_repository(target)
        config = root / "dual-skill.json"
        _write_composition_config(config, "skill")

        initial = self.composition("apply", target=target, config=config)
        if initial.get("status") != "applied":
            raise IntegrationError(f"unexpected initial Composition payload: {initial}")
        composition_before_policy = _snapshot(target, COMPOSITION_STATE_ROOTS)
        original_agents = (target / "AGENTS.md").read_bytes()

        self.adopt_policy_migration(target)
        _assert_snapshot_unchanged(
            target,
            COMPOSITION_STATE_ROOTS,
            composition_before_policy,
            label="Composition metadata during Policy adoption",
        )
        if not (target / ".agent-policy.lock").is_file():
            raise IntegrationError("dual fixture did not create .agent-policy.lock")
        if not (target / ".template-composition/lock.json").is_file():
            raise IntegrationError("dual fixture lost Composition lock")

        policy_agents = (target / "AGENTS.md").read_bytes()
        if policy_agents == original_agents:
            raise IntegrationError(
                "Policy migration did not perform the expected AGENTS.md ownership handoff"
            )

        composition_validation = self.composition("validate", target=target)
        if composition_validation.get("status") != "valid":
            raise IntegrationError(
                f"Composition validation rejected Policy-rewritten seed: {composition_validation}"
            )

        plan = self.composition("plan", target=target, mode="update")
        preserved = {
            entry.get("destination")
            for entry in plan.get("files", {}).get("preserve", [])
            if isinstance(entry, dict)
        }
        if "AGENTS.md" not in preserved:
            raise IntegrationError(
                f"managed update did not classify Policy-rewritten AGENTS.md as preserved seed: {plan}"
            )

        policy_before_composition = _snapshot(target, POLICY_STATE_ROOTS)
        agents_before_composition = (target / "AGENTS.md").read_bytes()
        updated = self.composition("apply", target=target, mode="update")
        if updated.get("status") != "updated":
            raise IntegrationError(f"unexpected Composition update payload: {updated}")
        _assert_snapshot_unchanged(
            target,
            POLICY_STATE_ROOTS,
            policy_before_composition,
            label="Policy metadata during Composition update",
        )
        if (target / "AGENTS.md").read_bytes() != agents_before_composition:
            raise IntegrationError("Composition update overwrote the Policy-rewritten AGENTS.md seed")

        composition_before_render = _snapshot(target, COMPOSITION_STATE_ROOTS)
        self.policy(target, "render")
        self.policy(target, "validate")
        _assert_snapshot_unchanged(
            target,
            COMPOSITION_STATE_ROOTS,
            composition_before_render,
            label="Composition metadata during Policy render/validate",
        )

    def reverse_order_fails_closed(self, root: Path) -> None:
        target = root / "reverse-order"
        _init_repository(target)
        self.adopt_policy_fresh(target)
        policy_before = _snapshot(target, POLICY_STATE_ROOTS)
        agents_before = (target / "AGENTS.md").read_bytes()

        config = root / "reverse-skill.json"
        _write_composition_config(config, "skill")
        payload = self.composition(
            "apply",
            target=target,
            config=config,
            expected=2,
        )
        if payload.get("status") != "conflict":
            raise IntegrationError(f"reverse-order Composition apply did not fail closed: {payload}")
        conflicts = payload.get("conflicts", [])
        if not any(str(item).startswith("AGENTS.md:") for item in conflicts):
            raise IntegrationError(
                f"reverse-order failure did not identify AGENTS.md handoff conflict: {payload}"
            )
        _assert_absent(
            target,
            COMPOSITION_STATE_ROOTS,
            label="Composition state after reverse-order conflict",
        )
        _assert_snapshot_unchanged(
            target,
            POLICY_STATE_ROOTS,
            policy_before,
            label="Policy metadata during reverse-order Composition conflict",
        )
        if (target / "AGENTS.md").read_bytes() != agents_before:
            raise IntegrationError("reverse-order Composition conflict changed Policy AGENTS.md")

    def run(self) -> None:
        self.verify_inputs()
        with tempfile.TemporaryDirectory(prefix="site-provider-coexistence-") as temporary:
            root = Path(temporary)
            self.policy_only(root)
            self.composition_only(root)
            self.dual_authority(root)
            self.reverse_order_fails_closed(root)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--composition-root", type=Path, required=True)
    parser.add_argument("--composition-python", type=Path, required=True)
    parser.add_argument("--composition-revision", required=True)
    parser.add_argument("--policy-root", type=Path, required=True)
    parser.add_argument("--policy-cli", type=Path, required=True)
    parser.add_argument("--policy-revision", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    harness = Harness(
        composition_root=args.composition_root,
        composition_python=args.composition_python,
        composition_revision=args.composition_revision,
        policy_root=args.policy_root,
        policy_cli=args.policy_cli,
        policy_revision=args.policy_revision,
    )
    try:
        harness.run()
    except IntegrationError as exc:
        print(f"provider coexistence validation failed: {exc}", file=os.sys.stderr)
        return 1
    print(
        "provider coexistence validation passed: policy-only, composition-only, "
        "dual-authority, and reverse-order fail-closed fixtures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
