"""Immutable real-input qualification, old findings and domain-owned resolution."""

import copy
import json

import pytest

from scripts.qualify_discovery_candidate import (
    SCRIPT,
    domain_projection,
    git_commit,
    materialize,
    module,
    preview,
    qualify,
    read_case,
    stage_candidate,
    write,
)


@pytest.mark.parametrize("authority", ["policy", "composition", "modeling", "integration", "site"])
def test_fixed_authority_source_and_distributed_qualification(authority, tmp_path):
    result = qualify(authority, tmp_path)
    assert result["source_distributed_equal"]
    assert result["selected"] and result["final_validation"]["valid"]
    assert result["candidate_result"] == "NO_UPDATE_REQUIRED"
    assert result["removed"] == (
        ["contracts/publication-bundle/README.md"] if authority == "site" else []
    )


def setup_case(authority, root):
    case = read_case(authority)
    materialize(case, root)
    git_commit(root)
    return case


def test_site_f1_f2_real_inventory_and_same_named_local_target(tmp_path):
    case = setup_case("site", tmp_path)
    agent = json.loads(case["files"]["agent.json"])
    old_adapter = json.loads(case["files"][".progressive-discovery.json"])
    assert agent["integration_contracts"]["authority_model"]["owner"] == "integration"
    assert "Modeling-owned" in old_adapter["exclusion_reasons"]["authority.json"]  # F1
    path = "contracts/publication-bundle/README.md"
    assert path in case["baseline_expected"] and (tmp_path / path).is_file()  # F2
    stage_candidate(case, tmp_path)
    candidate = module(SCRIPT, "site_candidate").run(
        tmp_path, candidate_v2=True, adapter_path=".candidate-discovery.json"
    )
    assert path not in candidate["expected_documents"]
    assert {"source": "agent.json", "namespace": "external", "value": path} in candidate[
        "references"
    ]
    assert "authority.json" not in candidate["exclusions"]


def test_composition_f3_scoped_omission_never_erases_root(tmp_path):
    case = setup_case("composition", tmp_path)
    target = "docs/guides/webmcp-capability.md"
    assert target not in case["baseline_expected"]
    stage_candidate(case, tmp_path)
    engine = module(SCRIPT, "composition_candidate")
    _, final, _ = preview(engine, tmp_path, case)
    assert final["validation"]["valid"]
    assert target in final["expected_documents"]
    root = tmp_path / "index.md"
    root.write_text("\n".join(line for line in root.read_text().splitlines() if target not in line))
    report = engine.run(tmp_path, candidate_v2=True, adapter_path=".candidate-discovery.json")
    assert f"root coverage missing: {target}" in report["validation"]["errors"]
    assert target not in (tmp_path / "docs/index.md").read_text()


def test_composition_f4_catalog_change_uses_actual_domain_resolver(tmp_path):
    case = setup_case("composition", tmp_path)
    old_script = (
        tmp_path
        / ".agents/skills/maintain-progressive-discovery/scripts"
        / "maintain_progressive_discovery.py"
    )
    old = module(old_script, "catalog_old_engine")
    old_expected, errors = old._expected_documents(
        tmp_path, {"authoritative_inventories": ["catalog/catalog.json"]}, ["catalog/catalog.json"]
    )
    assert old_expected == [] and not errors
    # Publication assets also contain recipes: manual expected_documents was redundant.
    catalog = json.loads(case["files"]["docs/publication-catalog.json"])
    assert "recipes/skill.json" in {item["source"] for item in catalog["assets"]}
    original = domain_projection(tmp_path)
    # Clone a valid domain recipe and add its ID to the canonical catalog.
    # Policy does not derive its path: unchanged Composition code does.
    recipe = json.loads((tmp_path / "recipes/skill.json").read_text())
    recipe["id"] = "skill-probe"
    write(tmp_path, "recipes/skill-probe.json", json.dumps(recipe))
    catalog = json.loads((tmp_path / "catalog/catalog.json").read_text())
    catalog["recipes"] = sorted(catalog["recipes"] + ["skill-probe"])
    write(tmp_path, "catalog/catalog.json", json.dumps(catalog))
    git_commit(tmp_path)
    updated = domain_projection(tmp_path)
    assert {x["path"] for x in updated["members"]} - {x["path"] for x in original["members"]} == {
        "recipes/skill-probe.json"
    }
    write(tmp_path, "discovery-members.json", json.dumps(original))
    write(tmp_path, ".candidate-discovery.json", json.dumps(case["adapter"]))
    engine = module(SCRIPT, "catalog_candidate")
    report = engine.run(tmp_path, candidate_v2=True, adapter_path=".candidate-discovery.json")
    assert "stale projection" in str(report["notes"])
    write(tmp_path, "discovery-members.json", json.dumps(updated))
    report = engine.run(tmp_path, candidate_v2=True, adapter_path=".candidate-discovery.json")
    assert "recipes/skill-probe.json" in report["expected_documents"]
    assert "root coverage missing: recipes/skill-probe.json" in report["validation"]["errors"]


@pytest.mark.parametrize("anchor", ["README.md", "AUTHORITY.md", "AGENTS.md"])
def test_modeling_f5_link_removal_is_rejected_only_by_candidate(tmp_path, anchor):
    case = setup_case("modeling", tmp_path)
    assert anchor not in case["baseline_expected"]
    old_script = (
        tmp_path
        / ".agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py"
    )
    old = module(old_script, "modeling_adopted")
    root = tmp_path / "index.md"
    original = root.read_text()
    root.write_text("\n".join(line for line in original.splitlines() if f"]({anchor})" not in line))
    assert old.run(tmp_path)["result"] == "NO_UPDATE_REQUIRED"
    root.write_text(original)
    stage_candidate(case, tmp_path)
    engine = module(SCRIPT, "modeling_candidate")
    _, final, _ = preview(engine, tmp_path, case)
    assert final["validation"]["valid"]
    root.write_text(
        "\n".join(line for line in root.read_text().splitlines() if f"]({anchor})" not in line)
    )
    report = engine.run(tmp_path, candidate_v2=True, adapter_path=".candidate-discovery.json")
    assert f"root coverage missing: {anchor}" in report["validation"]["errors"]


def test_old_d1_d2_d3_use_actual_adopted_parser(tmp_path):
    case = setup_case("composition", tmp_path)
    old = module(
        tmp_path
        / ".agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py",
        "old_findings",
    )
    adapter = json.loads(case["files"][".progressive-discovery.json"])
    expected, errors = old._expected_documents(
        tmp_path, adapter, old._discover_inventory_paths(tmp_path, adapter)
    )
    assert not errors
    assert not any(path.startswith("components/") for path in expected)  # D1
    # Independent authored index plus ancestor shortcut conflicts in old classification.
    write(tmp_path, "docs/guides/index.md", "# Guides\n[Concepts](composition-concepts.md)\n")
    report = old.run(tmp_path)
    item = next(x for x in report["classification"] if x["index"] == "docs/guides/index.md")
    assert item["classification"] == "authority-needed"  # D2
    root = tmp_path / "index.md"
    root.write_text(root.read_text() + "\nThis boundary explains responsibility.\n")
    assert "small index grammar" in str(old.run(tmp_path)["validation"]["errors"])  # D3


def test_snapshot_source_integrity_and_expected_not_index_derived(tmp_path):
    case = read_case("integration")
    changed = copy.deepcopy(case)
    changed["files"]["index.md"] += "\nTamper\n"
    with pytest.raises(ValueError, match="blob mismatch"):
        materialize(changed, tmp_path)
    materialize(case, tmp_path)
    stage_candidate(case, tmp_path)
    engine = module(SCRIPT, "independent_expected")
    before = engine.run(tmp_path, candidate_v2=True, adapter_path=".candidate-discovery.json")
    (tmp_path / "index.md").unlink()
    after = engine.run(tmp_path, candidate_v2=True, adapter_path=".candidate-discovery.json")
    assert before["expected_documents"] == after["expected_documents"]
    assert not after["validation"]["valid"]


@pytest.mark.parametrize("authority", ["composition", "modeling", "integration", "site"])
def test_canonical_consumer_gate_executes_candidate_and_rejects_mixed_version(authority, tmp_path):
    import subprocess
    import sys

    import yaml

    from agent_policy.lockfile import create_lock
    from agent_policy.renderer import render_skill

    case = setup_case(authority, tmp_path)
    stage_candidate(case, tmp_path)
    engine = module(SCRIPT, "formal_candidate_engine")
    _, final, _ = preview(engine, tmp_path, case)
    assert final["validation"]["valid"]
    write(
        tmp_path,
        ".progressive-discovery.json",
        (tmp_path / ".candidate-discovery.json").read_text(),
    )
    outputs = {}
    for relative, content in render_skill(
        "maintain-progressive-discovery", discovery_contract_version=2
    ).items():
        path = ".agents/skills/maintain-progressive-discovery/" + relative
        write(tmp_path, path, content)
        outputs[path] = tmp_path / path
    # Prospective isolated adoption only. Keep exact profile/skill selections.
    config = yaml.safe_load((tmp_path / ".agent-policy.yml").read_text())
    previous_contexts = copy.deepcopy(config["contexts"])
    revision = subprocess.check_output(
        ["git", "-C", str(SCRIPT.parents[3]), "rev-parse", "HEAD"], text=True
    ).strip()
    config["toolchain"]["revision"] = revision
    write(tmp_path, ".agent-policy.yml", yaml.safe_dump(config, sort_keys=False))
    assert (
        yaml.safe_load((tmp_path / ".agent-policy.yml").read_text())["contexts"]
        == previous_contexts
    )
    write(
        tmp_path,
        ".agent-policy.lock",
        create_lock(
            "TakashiSasaki/templates",
            revision,
            {".agent-policy.yml": tmp_path / ".agent-policy.yml"},
            outputs,
        ),
    )

    def gate():
        if authority == "modeling":
            command = (
                "import sys; from pathlib import Path; "
                "sys.path.insert(0, str(Path(sys.argv[1])/'tools')); "
                "import qualify; qualify.check_progressive_discovery(Path(sys.argv[1]))"
            )
            result = subprocess.run(
                [sys.executable, "-c", command, str(tmp_path)], capture_output=True, text=True
            )
            assert result.returncode == 0, result.stdout + result.stderr
        else:
            path = (
                "tests/test_progressive_discovery_source.py"
                if authority == "site"
                else "tests/test_repository_discovery.py"
            )
            test_module = module(tmp_path / path, "formal_" + authority)
            test_module.ROOT = tmp_path
            if authority == "site":
                classes = [
                    v
                    for v in vars(test_module).values()
                    if isinstance(v, type)
                    and hasattr(
                        v, "test_mixed_discovery_contracts_remain_expected_source_documents"
                    )
                ]
                classes[0]().test_mixed_discovery_contracts_remain_expected_source_documents()
            else:
                test_module.RepositoryDiscoveryTests().require_clean(tmp_path)

    gate()  # Actual unchanged canonical source invokes actual candidate distributed CLI.
    write(tmp_path, ".progressive-discovery.json", case["files"][".progressive-discovery.json"])
    with pytest.raises((AssertionError, subprocess.CalledProcessError)):
        gate()  # New runtime must not accept old adapter via formal qualification.
