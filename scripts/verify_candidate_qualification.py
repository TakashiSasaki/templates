#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def qualify_candidate(source_root: Path) -> None:
    from agent_policy.commands import check, render
    from agent_policy.identity import resolve_toolchain_revision

    candidate_revision = resolve_toolchain_revision()

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
        if f"TakashiSasaki/templates@{candidate_revision}" not in agents_content:
            raise RuntimeError("Candidate output missing candidate revision provenance")
        if not (fixture_root / ".agent-policy.lock").is_file():
            raise RuntimeError("Candidate qualification missing lockfile")


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qualify candidate Policy package internally.")
    parser.add_argument("--source-root", type=Path, default=ROOT)
    args = parser.parse_args(arguments)
    try:
        qualify_candidate(args.source_root.resolve())
        print(f"POLICY_CANDIDATE_QUALIFICATION_PASS source_root={args.source_root.resolve()}")
        return 0
    except Exception as exc:
        print(f"POLICY_CANDIDATE_QUALIFICATION_FAIL error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
