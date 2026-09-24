#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def resolve_checkout_revision(repo_root: Path) -> str:
    try:
        rev = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except Exception as exc:
        raise RuntimeError(f"Failed to resolve checkout revision in {repo_root}: {exc}") from exc
    if not rev or len(rev) != 40 or not all(c in "0123456789abcdef" for c in rev):
        raise ValueError(f"Invalid checkout revision '{rev}' in {repo_root}")
    return rev


def _verify_source_and_resources_bound(repo_root: Path) -> None:
    src_dir = (repo_root / "src").resolve()
    if not src_dir.is_dir():
        raise RuntimeError(f"Source checkout missing src directory at {src_dir}")

    if str(src_dir) not in sys.path or sys.path[0] != str(src_dir):
        sys.path.insert(0, str(src_dir))

    import agent_policy
    import agent_policy.config

    agent_policy_path = Path(agent_policy.__file__).resolve()
    if not agent_policy_path.is_relative_to(src_dir):
        raise RuntimeError(
            f"agent_policy imported from {agent_policy_path}, expected under {src_dir}"
        )

    pkg_root = agent_policy.config.package_root().resolve()
    if pkg_root != repo_root.resolve():
        raise RuntimeError(
            f"agent_policy package_root() resolved to {pkg_root}, expected {repo_root.resolve()}"
        )


def qualify_candidate() -> str:
    _verify_source_and_resources_bound(ROOT)
    from agent_policy.commands import check, render

    candidate_revision = resolve_checkout_revision(ROOT)

    with tempfile.TemporaryDirectory(prefix="policy-candidate-qualification-") as temporary:
        fixture_root = Path(temporary) / "repo"
        fixture_root.mkdir()
        (fixture_root / ".git").mkdir()

        config_content = f"""schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {candidate_revision}
contexts:
  coding:
    profiles:
      - core
      - security-baseline
      - pull-request
      - progressive-discovery
    project_policy:
      files: []
outputs:
  agents:
    enabled: true
    path: AGENTS.md
    context: coding
    renderer: agents-md
skills:
  enabled:
    - pr-review
    - orchestrate-repository-change
    - maintain-progressive-discovery
"""
        (fixture_root / ".agent-policy.yml").write_text(config_content, encoding="utf-8")

        # 1. Render candidate consumer outputs using candidate package semantics
        render_diagnostics = render.run(fixture_root, ".agent-policy.yml")
        if render_diagnostics:
            raise RuntimeError(f"Candidate render failed: {render_diagnostics}")

        # 2. Check candidate consumer outputs using candidate package semantics
        check_diagnostics = check.run(fixture_root, ".agent-policy.yml")
        if check_diagnostics:
            raise RuntimeError(f"Candidate check failed: {check_diagnostics}")

        # 3. Verify candidate output coherence and provenance
        agents_content = (fixture_root / "AGENTS.md").read_text(encoding="utf-8")
        expected_provenance = f"TakashiSasaki/templates@{candidate_revision}"
        if expected_provenance not in agents_content:
            raise RuntimeError(
                f"Candidate output missing candidate revision provenance: "
                f"expected {expected_provenance}"
            )
        if not (fixture_root / ".agent-policy.lock").is_file():
            raise RuntimeError("Candidate qualification missing lockfile")

        return candidate_revision


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qualify candidate Policy package internally.")
    parser.parse_args(arguments)
    try:
        candidate_revision = qualify_candidate()
        print(
            f"POLICY_CANDIDATE_QUALIFICATION_PASS revision={candidate_revision} source_root={ROOT}"
        )
        return 0
    except Exception as exc:
        print(f"POLICY_CANDIDATE_QUALIFICATION_FAIL error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
