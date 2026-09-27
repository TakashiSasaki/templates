"""Exercise actual candidate parser, engine, CLI and rendered distribution."""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py"


def load(path=SCRIPT):
    spec = importlib.util.spec_from_file_location("discovery_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content if isinstance(content, str) else json.dumps(content))


def entry(path, kind="file"):
    return {"path": path, "kind": kind}


def fixture(root):
    write(
        root,
        ".agent-policy.yml",
        (ROOT / "tests/fixtures/progressive-discovery/simple-docs/.agent-policy.yml").read_text(),
    )
    write(root, "README.md", "# Readme\n")
    write(
        root, "index.md", "# Entry\n\nA boundary paragraph without a link.\n\n[Readme](README.md)\n"
    )
    return {"schema_version": 2, "entries": [entry("README.md")]}


def run(root, adapter, *, apply=False, engine=None):
    write(root, ".progressive-discovery.json", adapter)
    return (engine or load()).run(root, candidate_v2=True, apply=apply)


def clean(report):
    assert report["policy_selected"]
    assert report["validation"]["valid"], report["validation"]["errors"]
    assert report["result"] == "NO_UPDATE_REQUIRED", report["plan"]


def test_prose_no_frontmatter_and_dry_run_no_changes(tmp_path):
    adapter = fixture(tmp_path)
    write(tmp_path, ".progressive-discovery.json", adapter)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    clean(load().run(tmp_path, candidate_v2=True))
    assert before == {
        p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"schema_version": 9},
        {"schema_version": "2"},
        {"schema_version": 1},
        {"entries": []},
        {"extra": True},
        {"entries": [entry("README.md") | {"unknown": 1}]},
        {"entries": [entry("../bad")]},
        {"exclude": [{"path": "README.md", "reason": "conflict"}]},
        {"entries": [entry("README.md"), entry("README.md", "directory")]},
        {"retire": [{"path": "index.md", "reason": "root"}]},
    ],
)
def test_malformed_candidate(tmp_path, bad):
    adapter = fixture(tmp_path)
    if not bad:
        del adapter["schema_version"]
    else:
        adapter.update(bad)
    report = run(tmp_path, adapter)
    assert not report["validation"]["valid"]
    assert report["result"] == "AUTHORITY_NEEDED"
    assert report["plan"] == []


def test_version_cross_pair_and_duplicate_key(tmp_path):
    adapter = fixture(tmp_path)
    write(tmp_path, ".progressive-discovery.json", adapter)
    assert not load().run(tmp_path)["validation"]["valid"]
    write(tmp_path, ".progressive-discovery.json", '{"schema_version":2,"schema_version":2}')
    report = load().run(tmp_path, candidate_v2=True)
    assert "duplicate" in str(report["notes"]).lower()


def inventory(path="inventory.json", at=None, namespace="local", kind="file"):
    return {
        "path": path,
        "format": "json",
        "select": [{"at": at or ["members", "*", "source"], "namespace": namespace, "kind": kind}],
    }


@pytest.mark.parametrize(
    "payload",
    [None, "{", '{"members":[],"members":[]}', {"wrong": []}, {"members": {}}, {"members": [4]}],
)
def test_inventory_fail_closed(tmp_path, payload):
    adapter = fixture(tmp_path)
    adapter["inventories"] = [inventory()]
    if payload is not None:
        write(tmp_path, "inventory.json", payload)
    report = run(tmp_path, adapter)
    assert not report["validation"]["valid"]
    assert report["plan"] == []


def test_yaml_invalid_and_unsupported_format(tmp_path):
    adapter = fixture(tmp_path)
    adapter["inventories"] = [inventory("inventory.yml") | {"format": "yaml"}]
    write(tmp_path, "inventory.yml", "members: []\nmembers: []\n")
    assert not run(tmp_path, adapter)["validation"]["valid"]
    adapter["inventories"][0]["format"] = "xml"
    assert not run(tmp_path, adapter)["validation"]["valid"]


def test_mixed_namespaces_and_inventory_discoverability(tmp_path):
    adapter = fixture(tmp_path)
    write(
        tmp_path,
        "inventory.json",
        {"local": "README.md", "foreign": "contracts/a.md", "url": "/deployed/index.md"},
    )
    write(tmp_path, "contracts/a.md", "# Same spelling\n")
    adapter["inventories"] = [inventory(at=["local"])]
    adapter["inventories"][0]["select"] += [
        inventory(at=["foreign"], namespace="external")["select"][0],
        inventory(at=["url"], namespace="deployment")["select"][0],
    ]
    write(tmp_path, "index.md", "# Entry\n[Readme](README.md)\n[Inventory](inventory.json)\n")
    report = run(tmp_path, adapter)
    clean(report)
    assert "contracts/a.md" not in report["expected_documents"]
    assert len(report["references"]) == 2
    write(tmp_path, "index.md", "# Entry\n[Readme](README.md)\n")
    assert not run(tmp_path, adapter)["validation"]["valid"]


def test_omission_preserves_root_coverage_and_nested_shortcuts(tmp_path):
    adapter = fixture(tmp_path)
    adapter["entries"] += [
        entry("docs/private.md"),
        entry("docs/public.md"),
        entry("docs/index.md", "index"),
    ]
    adapter["omit_from"] = [
        {
            "index": "docs/index.md",
            "paths": ["docs/private.md"],
            "reason": "Source-only; root routes it",
        }
    ]
    write(tmp_path, "docs/index.md", "# Docs\n\nReader boundary.\n\n[Public](public.md)\n")
    for p in ("docs/private.md", "docs/public.md"):
        write(tmp_path, p, "# Document\n")
    write(
        tmp_path,
        "index.md",
        "# Root\n[Readme](README.md)\n[Private](docs/private.md)\n"
        "[Docs](docs/)\n[Shortcut](docs/public.md)\n",
    )
    clean(run(tmp_path, adapter))
    write(tmp_path, "index.md", "# Root\n[Readme](README.md)\n[Docs](docs/index.md)\n")
    report = run(tmp_path, adapter)
    assert "docs/private.md" in report["expected_documents"]
    assert "root coverage missing: docs/private.md" in report["validation"]["errors"]


@pytest.mark.parametrize("link", ["docs/#heading", "docs/index.md#heading"])
def test_directory_index_fragments_and_missing_anchors(tmp_path, link):
    adapter = fixture(tmp_path)
    adapter["entries"].append(entry("docs", "directory"))
    write(tmp_path, "docs/index.md", "# Docs\n\n## Heading\n")
    write(tmp_path, "index.md", f"# Root\n[Readme](README.md)\n[Docs]({link})\n")
    clean(run(tmp_path, adapter))
    write(tmp_path, "docs/index.md", "# Docs\n\n```md\n## Heading\n```\n")
    assert not run(tmp_path, adapter)["validation"]["valid"]


@pytest.mark.parametrize(
    "example",
    [
        "`[Readme](README.md)`",
        "<!-- [Readme](README.md) -->",
        "```md\n[Readme](README.md)\n```",
        "    [Readme](README.md)",
        "> [Readme](README.md)",
    ],
)
def test_examples_do_not_count_as_navigation(tmp_path, example):
    adapter = fixture(tmp_path)
    write(tmp_path, "index.md", "# Root\n\n" + example + "\n")
    assert "root coverage missing: README.md" in run(tmp_path, adapter)["validation"]["errors"]


def test_delegation_preserves_entry_but_not_all_files(tmp_path):
    adapter = fixture(tmp_path)
    write(tmp_path, "vendor/entry.md", "# Entry\n")
    write(tmp_path, "vendor/deep/index.md", "---\nfixture: true\n---\n")
    adapter["delegate"] = [
        {
            "path": "vendor",
            "entry": entry("vendor/entry.md"),
            "reason": "Domain inventory owns interior",
        }
    ]
    write(tmp_path, "index.md", "# Root\n[Readme](README.md)\n[Vendor](vendor/entry.md)\n")
    clean(run(tmp_path, adapter))
    write(tmp_path, "index.md", "# Root\n[Readme](README.md)\n[Directory](vendor/)\n")
    assert not run(tmp_path, adapter)["validation"]["valid"]


def test_projection_stale_missing_closure_and_kind(tmp_path):
    adapter = fixture(tmp_path)
    write(tmp_path, "domain.json", {"ids": ["a"]})
    digest = hashlib.sha256((tmp_path / "domain.json").read_bytes()).hexdigest()
    projection = {
        "schema_version": 1,
        "sources": [{"path": "domain.json", "sha256": digest}],
        "members": [entry("README.md")],
    }
    write(tmp_path, "projection.json", projection)
    adapter["projections"] = [{"path": "projection.json", "sources": ["domain.json"]}]
    write(
        tmp_path,
        "index.md",
        "# Root\n[Readme](README.md)\n[Domain](domain.json)\n[Projection](projection.json)\n",
    )
    clean(run(tmp_path, adapter))
    write(tmp_path, "domain.json", {"ids": ["a", "b"]})
    assert "stale projection" in str(run(tmp_path, adapter)["notes"])
    adapter["projections"][0]["sources"] = ["other.json"]
    assert "closure mismatch" in str(run(tmp_path, adapter)["notes"])


def test_symlink_input_and_orphan_and_frontmatter(tmp_path):
    adapter = fixture(tmp_path)
    (tmp_path / "alias.md").symlink_to(tmp_path / "README.md")
    adapter["entries"].append(entry("alias.md"))
    assert not run(tmp_path, adapter)["validation"]["valid"]
    adapter["entries"].pop()
    write(tmp_path, "nested/index.md", "# Nested\n")
    assert "orphan index: nested/index.md" in run(tmp_path, adapter)["validation"]["errors"]
    write(
        tmp_path,
        "index.md",
        "---\nx: y\n---\n# Root\n[Readme](README.md)\n[Nested](nested/index.md)\n",
    )
    assert "front matter" in str(run(tmp_path, adapter)["validation"]["errors"])


def test_generated_apply_reuses_engine_and_is_idempotent(tmp_path):
    adapter = fixture(tmp_path)
    write(tmp_path, "docs/a.md", "# A\n")
    adapter["entries"].append(entry("docs/a.md"))
    adapter["generated"] = [
        {"path": "docs/index.md", "title": "Docs", "section": "Members", "members": ["docs/a.md"]}
    ]
    write(tmp_path, "index.md", "# Root\n[Readme](README.md)\n[Docs](docs/index.md)\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    original = (tmp_path / "index.md").read_bytes()
    first = run(tmp_path, adapter, apply=True)
    clean(first)
    assert "create docs/index.md" in first["applied"]
    second = run(tmp_path, adapter, apply=True)
    clean(second)
    assert second["applied"] == []
    assert (tmp_path / "index.md").read_bytes() == original
    write(tmp_path, "docs/index.md", "# Authored\n")
    report = run(tmp_path, adapter, apply=True)
    assert report["result"] == "AUTHORITY_NEEDED"
    assert (tmp_path / "docs/index.md").read_text() == "# Authored\n"


def test_cli_and_distribution_use_identical_schema(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    adapter = fixture(repo)
    write(repo, ".progressive-discovery.json", adapter)
    rendered = render_skill("maintain-progressive-discovery")
    dist = tmp_path / "distributed"
    for path, content in rendered.items():
        write(dist, path, content)
    distributed = dist / "scripts/maintain_progressive_discovery.py"
    reports = []
    for path in (SCRIPT, distributed):
        result = subprocess.run(
            [sys.executable, str(path), "--root", str(repo), "--candidate-v2", "--format", "json"],
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        clean(report)
        reports.append(report)
    assert reports[0] == reports[1]
    assert "{{ canonical_" not in (dist / "scripts/discovery_candidate.py").read_text()
    assert load(distributed).run(repo)["result"] == "AUTHORITY_NEEDED"
