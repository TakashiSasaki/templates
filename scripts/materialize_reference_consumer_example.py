#!/usr/bin/env python3
"""Temporarily materialize the reference-consumer example in an Actions checkout."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(path: str, value) -> None:
    (ROOT / path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def close_existing_product() -> None:
    run(
        "python",
        ".template-composition/checkpoint.py",
        "product",
        "--id",
        "site-reference-adoption-product",
        "--from",
        "site-reference-adoption",
    )


def prepare_planning_state() -> dict:
    manifest = load("site-manifest.json")
    if not any(
        isinstance(item, dict) and item.get("document") == "reference-consumer"
        for item in manifest["navigation"]
    ):
        manifest["navigation"].insert(
            2,
            {
                "title": "This repository as a reference consumer",
                "publication": "site",
                "document": "reference-consumer",
                "destination": "reference-consumer/index.md",
            },
        )
    write("site-manifest.json", manifest)
    run("python", "scripts/site_website_contract.py", "--write")

    offline = load("contracts/pwa-offline.json")
    route_id = "site-reference-consumer"
    if route_id not in offline["controlledRouteIds"]:
        anchor = offline["controlledRouteIds"].index(
            "site-policy-composition-coexistence"
        ) + 1
        offline["controlledRouteIds"].insert(anchor, route_id)
    if not any(item.get("routeId") == route_id for item in offline["routePolicies"]):
        anchor = next(
            i
            for i, item in enumerate(offline["routePolicies"])
            if item.get("routeId") == "site-policy-composition-coexistence"
        ) + 1
        offline["routePolicies"].insert(
            anchor,
            {
                "routeId": route_id,
                "offlinePolicy": "cached-content-when-available",
            },
        )
    write("contracts/pwa-offline.json", offline)

    for path in (
        "contracts/pwa-manifest.json",
        "contracts/pwa-offline.json",
        "contracts/pwa-update.json",
    ):
        data = load(path)
        data["mode"] = "planning"
        write(path, data)

    product = load("contracts/implementation-evidence.json")
    planned = []
    for requirement in product["requirements"]:
        targets = requirement.get("targets")
        if not isinstance(targets, list) or not targets:
            raise RuntimeError(
                f"requirement lacks retained planning targets: {requirement.get('id')}"
            )
        planned.append(
            {
                "id": requirement["id"],
                "description": requirement["description"],
                "targets": targets,
                "recordIds": [],
                "requiredPositiveProofKinds": requirement[
                    "requiredPositiveProofKinds"
                ],
            }
        )
    for contract_id, item_kind in (
        ("site_structure", "page"),
        ("document_metadata", "page-metadata"),
    ):
        requirement_id = (
            "site-structure-" if contract_id == "site_structure" else "document-metadata-"
        ) + route_id
        planned.append(
            {
                "id": requirement_id,
                "description": f"Site fulfills {requirement_id}",
                "targets": [
                    {
                        "kind": "contract-item",
                        "contractId": contract_id,
                        "itemKind": item_kind,
                        "itemId": route_id,
                    }
                ],
                "recordIds": [],
                "requiredPositiveProofKinds": ["end-to-end-test"],
            }
        )

    write(
        "contracts/implementation-evidence.json",
        {
            "$schema": product["$schema"],
            "schemaVersion": product["schemaVersion"],
            "mode": "planning",
            "commands": [],
            "releaseGates": [],
            "records": [],
            "requirements": planned,
        },
    )
    return product


def checkpoint_planning() -> None:
    run("python", ".template-composition/validate.py", ".", "--format", "json")
    run(
        "python",
        ".template-composition/checkpoint.py",
        "planning",
        "--id",
        "reference-consumer-page",
    )


def write_reader_sources() -> None:
    page = '''# `TakashiSasaki/templates` as a reference consumer

Most repositories should consume these systems from a separate product repository. This repository deliberately goes further: it uses the systems it provides to define and maintain its own Site. That makes the default `site` authority a concrete, executable reference consumer rather than only a documentation publisher.

## The normal relationship

```text
TakashiSasaki/templates
        |
        | provides Composition and Policy
        v
a separate consumer repository
```

That is still the recommended shape for ordinary users. The self-hosting case exists to demonstrate that the same contracts work on a mature, real repository.

## What this repository consumes

```text
Composition authority                    Policy authority
        |                                      |
        | Website + PWA contracts              | coding/review policy
        v                                      v
Site as a product                       Site maintenance
        \\                                      /
         \\                                    /
          +------ TakashiSasaki/templates ----+
```

The two consumer relationships are independent. Composition defines what the Site Website/PWA product is. Policy governs how maintainers and coding agents change and review the Site repository. The deployed Website runtime is not a Policy consumer.

| Concern | Canonical repository surface | What it demonstrates |
| --- | --- | --- |
| Composition intent | `composition.json` | The Site selects the `website` recipe with `capability.pwa`. |
| Composition managed state | `.template-composition/lock.json` | Exact provider source, resolved components, and managed/seed/generated ownership are explicit. |
| Policy selection | `.agent-policy.yml` | Site maintenance selects shared coding and review profiles plus repository-local policy. |
| Policy managed state | `.agent-policy.lock` | Generated Policy outputs are checked against the pinned immutable toolchain. |
| Site-specific maintenance rules | `policy/project.md` | Repository-specific normative constraints stay local instead of becoming shared Policy semantics. |
| Procedural maintenance workflows | `.agents/skills/` | Site-specific procedures remain Skills rather than being folded into Policy or Composition. |
| Agent-facing projection | `AGENTS.md` | Maintainer instructions are generated from the selected Policy context. |
| Reviewer-facing projection | `.review-authority/review-policy.md` | Review instructions are also generated and freshness-checked by Policy. |
| Self-hosting discovery | `reference-consumer.json` | Machines can discover the two consumer relationships without parsing this page. |
| Policy CI | `.github/workflows/check-agent-policy.yml` | CI verifies that Policy configuration, lock, and generated outputs remain synchronized. |
| Reference-consumer CI | `.github/workflows/reference-consumer.yml` | CI validates Composition state and exercises the real Website/PWA artifact. |
| Site build | `.github/workflows/build-pages.yml` | The consumer is validated as the same Pages artifact that Site publishes. |
| Publication selection | `publication-sources.json` | Reader publication revisions remain separate from consumer/runtime revisions. |

## Why immutable revisions do not create a cycle

Self-hosting is temporal rather than circular. A known immutable Composition or Policy revision **N** governs a later Site consumer revision **N+1**. The provider revision, consumer semantic source, Policy runtime, generated projection, and reader publication revision can therefore differ without contradiction.

This distinction matters: advancing what the Site publishes does not silently upgrade its own consumer state, and adopting a provider candidate does not automatically publish that candidate to readers.

## The maintenance path is part of the demonstration

A maintainer editing this repository is not following an unrelated handwritten process. The Site's `.agent-policy.yml` selects Policy, `policy/project.md` adds Site-local normative constraints, and Policy generates the current `AGENTS.md` and reviewer policy. Site-local Skills provide concrete procedures. CI then checks those generated outputs and the independent Composition consumer state.

The result is a useful dogfooding loop: provider semantics are exercised by a real consumer, while authority ownership stays separated. When Site adoption exposed generic Composition gaps, those gaps were fixed in Composition rather than hidden behind Site-only exceptions.

## What this page is — and is not

This page is a Site-owned explanation and example. It does not become a new semantic authority above Composition or Policy. Canonical state remains in the files listed above, and the generated section below is derived from that state. See also the [Policy–Composition coexistence contract](/coexistence/), the [machine-readable reference-consumer description](/reference-consumer.json), and the [published source browser](/files/).
'''
    (ROOT / "docs/reference-consumer.md").write_text(page, encoding="utf-8")

    catalog = load("docs/publication-catalog.json")
    if not any(item["id"] == "reference-consumer" for item in catalog["documents"]):
        index = next(
            i
            for i, item in enumerate(catalog["documents"])
            if item["id"] == "policy-composition-coexistence"
        ) + 1
        catalog["documents"].insert(
            index,
            {
                "id": "reference-consumer",
                "source": "docs/reference-consumer.md",
                "optional": False,
                "home": False,
            },
        )
    write("docs/publication-catalog.json", catalog)

    landing_path = ROOT / "docs/landing.md"
    landing = landing_path.read_text(encoding="utf-8")
    anchor = '<p>Clone or create your product repository separately. The provider-owned tutorials tell you what to install or run there. The <code>templates</code> repository itself is primarily the source of the tooling, contracts, and documentation.</p>\n</section>\n'
    panel = '''
<section class="portal-policy-panel" aria-labelledby="portal-reference-consumer-title">
  <span class="portal-policy-panel__icon"><img src="images/icon-policy.svg" alt=""></span>
  <div class="portal-policy-panel__copy">
    <p class="portal-policy-panel__label">Concrete reference consumer</p>
    <h2 id="portal-reference-consumer-title">See this repository consume its own systems</h2>
    <p><code>TakashiSasaki/templates</code> is also an executable example: Composition defines the Site Website/PWA product, while Policy governs repository maintenance and generated agent/review instructions.</p>
  </div>
  <a class="portal-policy-panel__action" href="reference-consumer/">Explore the reference consumer <span aria-hidden="true">→</span></a>
</section>
'''
    if "portal-reference-consumer-title" not in landing:
        if anchor not in landing:
            raise RuntimeError("English landing insertion anchor not found")
        landing = landing.replace(anchor, anchor + panel, 1)
    glossary = '    <a class="portal-doc-link" href="/glossary/">Glossary</a>'
    link = '    <a class="portal-doc-link" href="reference-consumer/">This repository as a reference consumer</a>\n'
    if link.strip() not in landing:
        landing = landing.replace(glossary, link + glossary, 1)
    landing_path.write_text(landing, encoding="utf-8")

    ja_path = ROOT / "translations/ja/docs/landing.md"
    ja = ja_path.read_text(encoding="utf-8")
    ja_anchor = '<p>product repository は別に clone または作成します。provider-owned tutorial が、そこで何を install / run するかを説明します。<code>templates</code> repository 自体は主に tooling、contracts、documentation の供給元です。</p>\n</section>\n'
    ja_panel = '''
<section class="portal-policy-panel" aria-labelledby="portal-reference-consumer-title">
  <span class="portal-policy-panel__icon"><img src="/images/icon-policy.svg" alt=""></span>
  <div class="portal-policy-panel__copy">
    <p class="portal-policy-panel__label">具体的な reference consumer</p>
    <h2 id="portal-reference-consumer-title">この repository 自身が自分の仕組みを使う例を見る</h2>
    <p><code>TakashiSasaki/templates</code> 自身も実行可能な利用例です。Composition が Site の Website/PWA product を定義し、Policy が repository maintenance と生成された agent/review instructions を規定します。</p>
  </div>
  <a class="portal-policy-panel__action" href="/reference-consumer/">Reference consumer を見る <span aria-hidden="true">→</span></a>
</section>
'''
    if "portal-reference-consumer-title" not in ja:
        if ja_anchor not in ja:
            raise RuntimeError("Japanese landing insertion anchor not found")
        ja = ja.replace(ja_anchor, ja_anchor + ja_panel, 1)
    ja_glossary = '    <a class="portal-doc-link" href="/glossary/">Glossary</a>'
    ja_link = '    <a class="portal-doc-link" href="/reference-consumer/">この repository を reference consumer として見る</a>\n'
    if ja_link.strip() not in ja:
        ja = ja.replace(ja_glossary, ja_link + ja_glossary, 1)
    ja_path.write_text(ja, encoding="utf-8")

    renderer_path = ROOT / "scripts/render_reference_consumer.py"
    renderer = renderer_path.read_text(encoding="utf-8")
    old = '    doc = root / "docs/policy-composition-coexistence.md"\n    text = insert_section(doc.read_text(), explanation(data))\n    translated_path = "translations/ja/docs/policy-composition-coexistence.md"'
    new = '    doc = root / "docs/policy-composition-coexistence.md"\n    text = insert_section(doc.read_text(), explanation(data))\n    example_path = "docs/reference-consumer.md"\n    example = insert_section((root / example_path).read_text(), explanation(data))\n    translated_path = "translations/ja/docs/policy-composition-coexistence.md"'
    if old not in renderer:
        raise RuntimeError("renderer insertion anchor not found")
    renderer = renderer.replace(old, new, 1)
    old_return = '    return {"assets/reference-consumer.json":json.dumps(data,indent=2,ensure_ascii=False)+"\\n",\n            "docs/policy-composition-coexistence.md":text,\n            translated_path:translated}'
    new_return = '    return {"assets/reference-consumer.json":json.dumps(data,indent=2,ensure_ascii=False)+"\\n",\n            "docs/policy-composition-coexistence.md":text,\n            example_path:example,\n            translated_path:translated}'
    if old_return not in renderer:
        raise RuntimeError("renderer return anchor not found")
    renderer_path.write_text(renderer.replace(old_return, new_return, 1), encoding="utf-8")


def restore_product_evidence(product: dict) -> None:
    route_id = "site-reference-consumer"
    for contract_id, item_kind in (
        ("site_structure", "page"),
        ("document_metadata", "page-metadata"),
    ):
        requirement_id = (
            "site-structure-" if contract_id == "site_structure" else "document-metadata-"
        ) + route_id
        target = {
            "kind": "contract-item",
            "contractId": contract_id,
            "itemKind": item_kind,
            "itemId": route_id,
        }
        if not any(record.get("id") == requirement_id for record in product["records"]):
            product["records"].append(
                {
                    "id": requirement_id,
                    "target": target,
                    "implementationBoundary": {
                        "status": "verified",
                        "description": f"Site publication assembly and browser implementation for {requirement_id}",
                        "locator": "scripts/assemble_publications_v3.py",
                    },
                    "releaseGateIds": ["site-reference"],
                    "positiveEvidence": [
                        {
                            "id": f"{requirement_id}-positive",
                            "status": "verified",
                            "kind": "end-to-end-test",
                            "description": "Actual browser contract assertions.",
                            "locator": "scripts/check_reference_website.py",
                            "commandId": "website-browser",
                            "expectedResult": "All reachable contract assertions pass; corrupted or unavailable states fail or expose the required fallback.",
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": f"{requirement_id}-negative",
                            "status": "verified",
                            "kind": "end-to-end-test",
                            "description": "Browser corruption or network/update failure assertions.",
                            "locator": "scripts/check_reference_website.py",
                            "commandId": "website-browser",
                            "expectedResult": "All reachable contract assertions pass; corrupted or unavailable states fail or expose the required fallback.",
                        }
                    ],
                }
            )
        if not any(req.get("id") == requirement_id for req in product["requirements"]):
            product["requirements"].append(
                {
                    "id": requirement_id,
                    "description": f"Site fulfills {requirement_id}",
                    "targets": [target],
                    "recordIds": [requirement_id],
                    "requiredPositiveProofKinds": ["end-to-end-test"],
                }
            )
    product["records"].sort(key=lambda item: item["id"])
    product["requirements"].sort(key=lambda item: item["id"])
    write("contracts/implementation-evidence.json", product)

    for path in (
        "contracts/pwa-manifest.json",
        "contracts/pwa-offline.json",
        "contracts/pwa-update.json",
    ):
        data = load(path)
        data["mode"] = "product"
        write(path, data)


def write_test() -> None:
    text = '''import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReferenceConsumerExampleTests(unittest.TestCase):
    def test_reader_example_is_canonical_and_reachable(self):
        catalog = json.loads((ROOT / "docs/publication-catalog.json").read_text())
        manifest = json.loads((ROOT / "site-manifest.json").read_text())
        self.assertIn("reference-consumer", {item["id"] for item in catalog["documents"]})
        leaves = []

        def visit(nodes):
            for node in nodes:
                if "children" in node:
                    visit(node["children"])
                else:
                    leaves.append(node)

        visit(manifest["navigation"])
        page = next(item for item in leaves if item.get("document") == "reference-consumer")
        self.assertEqual("reference-consumer/index.md", page["destination"])
        landing = (ROOT / "docs/landing.md").read_text()
        self.assertIn('href="reference-consumer/"', landing)

    def test_example_points_to_real_consumer_state(self):
        text = (ROOT / "docs/reference-consumer.md").read_text()
        for token in (
            "composition.json",
            ".template-composition/lock.json",
            ".agent-policy.yml",
            ".agent-policy.lock",
            "policy/project.md",
            ".agents/skills/",
            "AGENTS.md",
            ".review-authority/review-policy.md",
            ".github/workflows/check-agent-policy.yml",
            ".github/workflows/reference-consumer.yml",
            "publication-sources.json",
            "<!-- reference-consumer:start -->",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
'''
    (ROOT / "tests/test_reference_consumer_example.py").write_text(text, encoding="utf-8")


def bind_translation_blob() -> None:
    data = (ROOT / "docs/landing.md").read_bytes()
    blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    translations = load("translations/manifest.json")
    entry = next(
        item
        for item in translations["translations"]
        if item["canonical"] == "docs/landing.md" and item["language"] == "ja"
    )
    entry["canonical_blob_sha"] = blob
    write("translations/manifest.json", translations)


def collect() -> None:
    out = ROOT / "materialized"
    paths = [
        "docs/reference-consumer.md",
        "docs/landing.md",
        "translations/ja/docs/landing.md",
        "translations/manifest.json",
        "docs/publication-catalog.json",
        "site-manifest.json",
        "scripts/render_reference_consumer.py",
        "tests/test_reference_consumer_example.py",
        "contracts/routes.json",
        "contracts/site-structure.json",
        "contracts/document-metadata.json",
        "contracts/site-discovery.json",
        "contracts/pwa-offline.json",
        "contracts/pwa-manifest.json",
        "contracts/pwa-update.json",
        "contracts/implementation-evidence.json",
        "contracts/lifecycle-checkpoints.json",
        "docs/policy-composition-coexistence.md",
        "translations/ja/docs/policy-composition-coexistence.md",
        "assets/reference-consumer.json",
        "artifacts/lifecycle/002-site-reference-adoption-product",
        "artifacts/lifecycle/003-reference-consumer-page",
        "artifacts/lifecycle/004-reference-consumer-page-product",
    ]
    for relative in paths:
        source = ROOT / relative
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def main() -> None:
    close_existing_product()
    product = prepare_planning_state()
    checkpoint_planning()
    write_reader_sources()
    restore_product_evidence(product)
    write_test()
    bind_translation_blob()
    run("python", "scripts/render_reference_consumer.py", "--write")
    run("python", "scripts/site_website_contract.py")
    run("python", ".template-composition/validate.py", ".", "--format", "json")
    run(
        "python",
        ".template-composition/checkpoint.py",
        "product",
        "--id",
        "reference-consumer-page-product",
        "--from",
        "reference-consumer-page",
    )
    run("python", ".template-composition/validate.py", ".", "--format", "json")
    run(
        "python",
        "-m",
        "unittest",
        "tests.test_reference_consumer",
        "tests.test_reference_consumer_example",
        "tests.test_landing_page",
    )
    collect()


if __name__ == "__main__":
    main()
