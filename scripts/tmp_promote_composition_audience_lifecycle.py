#!/usr/bin/env python3
"""One-shot driver for the #838 Composition audience publication lifecycle promotion."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "contracts/implementation-evidence.json"
LEDGER = ROOT / "contracts/lifecycle-checkpoints.json"
COMPOSITION_REVISION = "6b7d764c963f957c6bee43c0c1d42eb03970ec8f"
PLANNING_ID = "composition-audience-publication-promotion"
PRODUCT_ID = "composition-audience-publication-promotion-product"
NEW_ITEMS = [
    ("document-metadata", "document_metadata", "page-metadata", "composition-publication-boundary", "composition-provider-maintenance"),
    ("document-metadata", "document_metadata", "page-metadata", "composition-publication-boundary", "composition-installer-release"),
    ("site-structure", "site_structure", "page", "composition-publication-boundary", "composition-provider-maintenance"),
    ("site-structure", "site_structure", "page", "composition-publication-boundary", "composition-installer-release"),
]


def run(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args), flush=True)
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=capture,
        check=True,
    )


def validate(label: str) -> None:
    print(f"=== canonical validation: {label} ===", flush=True)
    completed = subprocess.run(
        [sys.executable, str(ROOT / ".template-composition/validate.py"), str(ROOT), "--format", "json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, flush=True)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, flush=True)
    if completed.returncode != 0:
        raise SystemExit(f"canonical validation failed during {label}")
    payload = json.loads(completed.stdout)
    if payload.get("status") != "valid":
        raise SystemExit(f"canonical validation returned non-valid status during {label}: {payload.get('status')!r}")


def expanded_product(source: dict) -> dict:
    product = copy.deepcopy(source)
    if product.get("mode") != "product":
        raise SystemExit("expected current implementation-evidence mode product")
    records = {record["id"]: record for record in product["records"]}
    requirements = {req["id"]: req for req in product["requirements"]}
    for prefix, contract_id, item_kind, template_item, item_id in NEW_ITEMS:
        template_id = f"{prefix}-{template_item}"
        new_id = f"{prefix}-{item_id}"
        if new_id in records or new_id in requirements:
            raise SystemExit(f"evidence target already exists: {new_id}")
        if template_id not in records or template_id not in requirements:
            raise SystemExit(f"missing evidence template: {template_id}")

        record = copy.deepcopy(records[template_id])
        record["id"] = new_id
        record["target"] = {
            "kind": "contract-item",
            "contractId": contract_id,
            "itemKind": item_kind,
            "itemId": item_id,
        }
        boundary = record.get("implementationBoundary", {})
        boundary["description"] = f"Site publication assembly and browser implementation for {new_id}"
        record["implementationBoundary"] = boundary
        for field, suffix in (("positiveEvidence", "positive"), ("negativeEvidence", "negative")):
            proofs = record.get(field)
            if not isinstance(proofs, list) or len(proofs) != 1:
                raise SystemExit(f"unexpected {field} template shape for {template_id}")
            proofs[0]["id"] = f"{new_id}-{suffix}"
        records[new_id] = record

        requirement = copy.deepcopy(requirements[template_id])
        requirement["id"] = new_id
        requirement["description"] = f"Site fulfills {new_id}"
        requirement["targets"] = [copy.deepcopy(record["target"])]
        requirement["recordIds"] = [new_id]
        requirements[new_id] = requirement

    product["records"] = sorted(records.values(), key=lambda item: item["id"])
    product["requirements"] = sorted(requirements.values(), key=lambda item: item["id"])
    return product


def planning_from_baseline(baseline: dict, product: dict) -> dict:
    requirements = {req["id"]: copy.deepcopy(req) for req in baseline["requirements"]}
    product_requirements = {req["id"]: req for req in product["requirements"]}
    for prefix, _contract_id, _item_kind, _template_item, item_id in NEW_ITEMS:
        new_id = f"{prefix}-{item_id}"
        requirements[new_id] = copy.deepcopy(product_requirements[new_id])
    planning = copy.deepcopy(baseline)
    planning["mode"] = "planning"
    planning["commands"] = []
    planning["releaseGates"] = []
    planning["records"] = []
    projected = []
    for requirement in sorted(requirements.values(), key=lambda item: item["id"]):
        projected.append(
            {
                "id": requirement["id"],
                "description": requirement["description"],
                "targets": requirement["targets"],
                "recordIds": [],
                "requiredPositiveProofKinds": requirement["requiredPositiveProofKinds"],
            }
        )
    planning["requirements"] = projected
    return planning


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    head = run("git", "rev-parse", "HEAD", capture=True).stdout.strip()
    base = run("git", "merge-base", "origin/site", head, capture=True).stdout.strip()
    print(f"product head={head}\nplanning baseline={base}", flush=True)

    original_product = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    product = expanded_product(original_product)

    # A planning checkpoint must describe the pre-promotion product state plus
    # future requirements. Reconstruct that state transiently; do not commit it.
    run("git", "checkout", base, "--", ".")
    baseline = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    planning = planning_from_baseline(baseline, product)
    write_json(EVIDENCE, planning)
    validate("pre-promotion planning state")
    run(
        sys.executable,
        ".template-composition/checkpoint.py",
        "planning",
        "--id",
        PLANNING_ID,
        "--source-revision",
        COMPOSITION_REVISION,
    )
    planning_ledger = LEDGER.read_bytes()

    # Restore the exact #838 product tree, then retain the validated planning
    # ledger/snapshot and add the concrete evidence for the two promoted pages.
    run("git", "checkout", head, "--", ".")
    LEDGER.write_bytes(planning_ledger)
    write_json(EVIDENCE, product)
    validate("promoted product state before product checkpoint")
    run(
        sys.executable,
        ".template-composition/checkpoint.py",
        "product",
        "--id",
        PRODUCT_ID,
        "--from",
        PLANNING_ID,
        "--source-revision",
        COMPOSITION_REVISION,
    )

    run(sys.executable, "scripts/render_reference_consumer.py", "--write")

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    wanted = [
        next(item for item in ledger["checkpoints"] if item["id"] == PLANNING_ID),
        next(item for item in ledger["checkpoints"] if item["id"] == PRODUCT_ID),
    ]
    doc = ROOT / "docs/lifecycle.md"
    text = doc.read_text(encoding="utf-8")
    heading = "### Composition audience publication promotion history"
    if heading in text:
        raise SystemExit("lifecycle promotion history already documented")
    rows = "\n".join(
        f"| {item['sequence']} | {item['phase']} | {item['id']} | {item['snapshotPath']} | {item['manifestSha256']} |"
        for item in wanted
    )
    addition = (
        "\n\n### Composition audience publication promotion history\n\n"
        "These checkpoints bind the validated Site promotion of the already-qualified "
        "Composition audience records into the active publication mapping.\n\n"
        "| Sequence | Phase | ID | Snapshot | Manifest SHA-256 |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"{rows}\n"
    )
    doc.write_text(text.rstrip() + addition, encoding="utf-8")

    validate("final promoted product state")
    run(sys.executable, "-m", "unittest", "tests.test_ledger_overview", "tests.test_reference_consumer", "-v")
    run(sys.executable, "-I", "tests/test_composition_playground_cross_authority_workflow.py")
    run(sys.executable, "scripts/site_website_contract.py")
    run("git", "diff", "--check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
