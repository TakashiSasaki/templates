#!/usr/bin/env python3
"""Offline Stage A qualification against immutable consumer source fixtures.

This tool writes only its caller-owned temporary sandbox. It does not adopt Policy,
fetch code, execute configured hooks, or change a live authority checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import posixpath
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_policy.renderer import render_skill  # noqa: E402

CORPUS = ROOT / "tests/fixtures/discovery-consumers"
SCRIPT = ROOT / "skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py"


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def write(root, relative, text):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def read_case(authority):
    return json.loads((CORPUS / f"{authority}.json").read_text())


def materialize(case, root):
    engine = module(SCRIPT, "discovery_snapshot_engine")
    for path, content in case["files"].items():
        if engine._safe_relative(path) != path:
            raise ValueError(f"unsafe snapshot path: {path}")
        raw = content.encode()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != case["git_blobs"][path]:
            raise ValueError(f"source fixture blob mismatch: {path}")
        write(root, path, content)
    for path in case["directories"]:
        if engine._safe_relative(path) != path:
            raise ValueError(f"unsafe directory: {path}")
        (root / path).mkdir(parents=True, exist_ok=True)


def git_commit(root):
    for arguments in (
        ["init", "-q"],
        ["add", "."],
        [
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "isolated qualification input",
        ],
    ):
        subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )


def domain_projection(root):
    """Call Composition's captured, unchanged resolver; no Policy ID->path rule."""
    domain = module(root / "scripts/composer_core_impl.py", "discovery_composition_domain")
    state = domain.load_source_state()
    members = [
        {"path": domain._component_path(i).relative_to(root).as_posix(), "kind": "file"}
        for i in state.components
    ]
    members += [
        {"path": domain._recipe_path(i).relative_to(root).as_posix(), "kind": "file"}
        for i in state.recipes
    ]
    publication = domain.read_json(root / "docs/publication-catalog.json")
    members += [
        {"path": x["source"], "kind": "directory" if (root / x["source"]).is_dir() else "file"}
        for x in publication["assets"]
    ]
    members = list({(x["path"], x["kind"]): x for x in members}.values())
    return {
        "schema_version": 1,
        "sources": [
            {"path": p, "sha256": hashlib.sha256((root / p).read_bytes()).hexdigest()}
            for p in ["catalog/catalog.json", "docs/publication-catalog.json"]
        ],
        "members": members,
    }


def stage_candidate(case, root):
    for path, value in case.get("proposed_domain_inputs", {}).items():
        write(root, path, json.dumps(value, indent=2) + "\n")
    if case["projection"]:
        actual = domain_projection(root)
        if actual != case["projection"]:
            raise ValueError("Composition projection disagrees with immutable domain resolver")
        write(root, "discovery-members.json", json.dumps(actual, indent=2) + "\n")
    write(root, ".candidate-discovery.json", json.dumps(case["adapter"], indent=2) + "\n")


def preview(engine, root, case):
    """Propose links in the isolated sandbox only; expected input stays unchanged."""
    initial = engine.run(root, adapter_path=".candidate-discovery.json", candidate_v2=True)
    if initial["notes"]:
        raise ValueError(initial["notes"])
    before = {p: (root / p).read_text() for p in initial["indexes"]}
    # Render only declared generated indexes, via existing safe apply machinery.
    applied = engine.run(
        root, adapter_path=".candidate-discovery.json", candidate_v2=True, apply=True
    )
    if applied["apply_errors"]:
        raise ValueError(applied["apply_errors"])
    for error in applied["validation"]["errors"]:
        if error.startswith("root coverage missing: "):
            index, path = "index.md", error.removeprefix("root coverage missing: ")
        elif error.startswith("index coverage missing: "):
            index, path = error.removeprefix("index coverage missing: ").split(": ", 1)
        elif error.startswith("orphan index: "):
            index, path = "index.md", error.removeprefix("orphan index: ")
        else:
            raise ValueError(f"preview requires non-link decision: {error}")
        if index in {g["path"] for g in case["adapter"].get("generated", [])}:
            raise ValueError(f"generated coverage is incomplete: {error}")
        target = quote(posixpath.relpath(path, posixpath.dirname(index) or "."), safe="/.-_~")
        with (root / index).open("a") as output:
            output.write(f"\n- [{path}]({target}) - Candidate migration entry.\n")
    final = engine.run(root, adapter_path=".candidate-discovery.json", candidate_v2=True)
    changes = {
        p: (root / p).read_text()
        for p in final["indexes"]
        if p not in before or (root / p).read_text() != before[p]
    }
    return initial, final, changes


def qualify(authority, root):
    case = read_case(authority)
    materialize(case, root)
    git_commit(root)
    adopted_path = (
        root
        / ".agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py"
    )
    old = module(adopted_path, "discovery_adopted").run(root)
    if (
        old["expected_documents"] != case["baseline_expected"]
        or not old["policy_selected"]
        or not old["validation"]["valid"]
        or old["result"] != "NO_UPDATE_REQUIRED"
    ):
        raise ValueError(f"baseline reproduction failed: {authority}: {old['validation']}")
    stage_candidate(case, root)
    engine = module(SCRIPT, "discovery_candidate_engine")
    initial, final, changes = preview(engine, root, case)
    distributed = root / ".candidate-skill"
    for path, content in render_skill("maintain-progressive-discovery").items():
        write(distributed, path, content)
    reports = []
    for path in (SCRIPT, distributed / "scripts/maintain_progressive_discovery.py"):
        process = subprocess.run(
            [
                sys.executable,
                str(path),
                "--root",
                str(root),
                "--adapter",
                ".candidate-discovery.json",
                "--candidate-v2",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        report = json.loads(process.stdout)
        if (
            process.returncode
            or not report["policy_selected"]
            or not report["validation"]["valid"]
            or report["result"] != "NO_UPDATE_REQUIRED"
        ):
            raise ValueError(f"candidate qualification failed: {authority}: {report['validation']}")
        reports.append(report)
    if reports[0] != reports[1]:
        raise ValueError("source/distribution report mismatch")
    package = render_skill("maintain-progressive-discovery", discovery_contract_version=2)
    package_digest = hashlib.sha256(
        json.dumps(
            {p: hashlib.sha256(v.encode()).hexdigest() for p, v in sorted(package.items())},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {
        "candidate_package_sha256": package_digest,
        "authority": authority,
        "revision": case["revision"],
        "old_expected": old["expected_documents"],
        "candidate_expected": final["expected_documents"],
        "added": sorted(set(final["expected_documents"]) - set(old["expected_documents"])),
        "removed": sorted(set(old["expected_documents"]) - set(final["expected_documents"])),
        "initial_validation": initial["validation"],
        "final_validation": final["validation"],
        "candidate_result": final["result"],
        "selected": final["policy_selected"],
        "old_classification": old["classification"],
        "candidate_classification": final["classification"],
        "schema_sha256": final["schema_sha256"],
        "preview_indexes": changes,
        "references": final["references"],
        "source_distributed_equal": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = []
    with tempfile.TemporaryDirectory(prefix="discovery-candidate-") as temporary:
        for authority in ("policy", "composition", "modeling", "integration", "site"):
            root = Path(temporary) / authority
            root.mkdir()
            reports.append(qualify(authority, root))
    args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n")
    print("DISCOVERY_CANDIDATE_QUALIFIED authorities=5 source=5 distributed=5 selected=5 clean=5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
