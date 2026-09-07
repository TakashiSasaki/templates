from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

BASE = "6a8503a5249ae27cc0d288411de77cce73af736b"
TEMP_PATHS = {
    ".github/scripts/webmcp_s1_remediate.py",
    ".github/workflows/webmcp-s1-remediation.yml",
}


def run(*args: str, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return completed.stdout.strip()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one replacement target in {path}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--composition-root", type=Path, required=True)
    parser.add_argument("--policy-root", type=Path, required=True)
    args = parser.parse_args()
    site = args.site_root.resolve()
    composition = args.composition_root.resolve()
    policy = args.policy_root.resolve()

    changed_from_base = set(
        filter(None, run("git", "diff", "--name-only", f"{BASE}..HEAD", cwd=site).splitlines())
    )
    if changed_from_base != TEMP_PATHS:
        raise SystemExit(
            f"unexpected setup delta from {BASE}: {sorted(changed_from_base)!r}"
        )

    lifecycle = site / "docs/lifecycle.md"
    replace_once(
        lifecycle,
        "The current canonical Site history contains four validated checkpoints:",
        "The current canonical Site history contains six validated checkpoints:",
    )
    replace_once(
        lifecycle,
        "4  routes-v5-publication-product\n   phase: product\n   changeKind: specification-change\n   parentId: routes-v5-publication\n   snapshotPath: artifacts/lifecycle/004-routes-v5-publication-product\n   manifestSha256: c3ba91ed78fc90f780213b443182b17c38316d77d92f0151fb3d00392e77d9f1\n",
        "4  routes-v5-publication-product\n   phase: product\n   changeKind: specification-change\n   parentId: routes-v5-publication\n   snapshotPath: artifacts/lifecycle/004-routes-v5-publication-product\n   manifestSha256: c3ba91ed78fc90f780213b443182b17c38316d77d92f0151fb3d00392e77d9f1\n\n5  webmcp-reader-publication\n   phase: planning\n   changeKind: specification-change\n   parentId: routes-v5-publication-product\n   snapshotPath: artifacts/lifecycle/005-webmcp-reader-publication\n   manifestSha256: a6c587cac040a7929fe4fc020acd61843598b6447bd733795d83e2b7182104dc\n\n6  webmcp-reader-publication-product\n   phase: product\n   changeKind: specification-change\n   parentId: webmcp-reader-publication\n   snapshotPath: artifacts/lifecycle/006-webmcp-reader-publication-product\n   manifestSha256: 2b434f5636675eeacc0d6c4a9676f68a64c953abfada439b1306449ed31ea2a1\n",
    )
    replace_once(
        lifecycle,
        "The later `routes-v5-publication -> routes-v5-publication-product`\npair shows a specification change continuing the same linear history after the\ninitial product state. The root requirement/evidence ledger represents current\nproduct state while these snapshots preserve the validated states it passed\nthrough.",
        "The later `routes-v5-publication -> routes-v5-publication-product` and\n`webmcp-reader-publication -> webmcp-reader-publication-product` pairs show\nspecification changes continuing the same linear history after the initial\nproduct state. The root requirement/evidence ledger represents current product\nstate while these snapshots preserve the validated states it passed through.",
    )

    ja_lifecycle = site / "translations/ja/docs/lifecycle.md"
    replace_once(
        ja_lifecycle,
        "現在の canonical Site history には、次の4つの validated checkpoint が存在します。",
        "現在の canonical Site history には、次の6つの validated checkpoint が存在します。",
    )
    replace_once(
        ja_lifecycle,
        "4  routes-v5-publication-product\n   phase: product\n   changeKind: specification-change\n   parentId: routes-v5-publication\n   snapshotPath: artifacts/lifecycle/004-routes-v5-publication-product\n   manifestSha256: c3ba91ed78fc90f780213b443182b17c38316d77d92f0151fb3d00392e77d9f1\n",
        "4  routes-v5-publication-product\n   phase: product\n   changeKind: specification-change\n   parentId: routes-v5-publication\n   snapshotPath: artifacts/lifecycle/004-routes-v5-publication-product\n   manifestSha256: c3ba91ed78fc90f780213b443182b17c38316d77d92f0151fb3d00392e77d9f1\n\n5  webmcp-reader-publication\n   phase: planning\n   changeKind: specification-change\n   parentId: routes-v5-publication-product\n   snapshotPath: artifacts/lifecycle/005-webmcp-reader-publication\n   manifestSha256: a6c587cac040a7929fe4fc020acd61843598b6447bd733795d83e2b7182104dc\n\n6  webmcp-reader-publication-product\n   phase: product\n   changeKind: specification-change\n   parentId: webmcp-reader-publication\n   snapshotPath: artifacts/lifecycle/006-webmcp-reader-publication-product\n   manifestSha256: 2b434f5636675eeacc0d6c4a9676f68a64c953abfada439b1306449ed31ea2a1\n",
    )
    replace_once(
        ja_lifecycle,
        "後続の `routes-v5-publication -> routes-v5-publication-product` は、initial product state の後も同じ linear history 上で specification change が継続することを示します。root の requirement/evidence ledger が current product state を表す一方、これらの snapshot はそこへ至った validated state を保存します。",
        "後続の `routes-v5-publication -> routes-v5-publication-product` と `webmcp-reader-publication -> webmcp-reader-publication-product` は、initial product state の後も同じ linear history 上で specification change が継続することを示します。root の requirement/evidence ledger が current product state を表す一方、これらの snapshot はそこへ至った validated state を保存します。",
    )

    ja_caps = site / "translations/ja/docs/capabilities.md"
    replace_once(
        ja_caps,
        "- [Headless service interface](/capabilities/service/)\n",
        "- [Headless service interface](/capabilities/service/)\n- [WebMCP reader guide](/capabilities/webmcp/)\n",
    )
    replace_once(
        ja_caps,
        "- [Progressive Web App capability](/capabilities/pwa/)\n\n別の",
        "- [Progressive Web App capability](/capabilities/pwa/)\n- [WebMCP reader guide](/capabilities/webmcp/)\n\nWebMCP guide は reader 向けに adoption の判断と security 上の含意を説明します。canonical WebMCP capability / contract semantics は引き続き Composition が所有します。\n\n別の",
    )

    ledger_test = site / "tests/test_ledger_overview.py"
    replace_once(
        ledger_test,
        '                "routes-v5-publication-product",\n            ],\n        )\n        self.assertEqual([item["sequence"] for item in checkpoints], [1, 2, 3, 4])\n',
        '                "routes-v5-publication-product",\n                "webmcp-reader-publication",\n                "webmcp-reader-publication-product",\n            ],\n        )\n        self.assertEqual([item["sequence"] for item in checkpoints], [1, 2, 3, 4, 5, 6])\n',
    )
    replace_once(
        ledger_test,
        '            ["planning", "product", "planning", "product"],\n',
        '            ["planning", "product", "planning", "product", "planning", "product"],\n',
    )
    replace_once(
        ledger_test,
        '            ["initial", "initial", "specification-change", "specification-change"],\n',
        '            [\n                "initial",\n                "initial",\n                "specification-change",\n                "specification-change",\n                "specification-change",\n                "specification-change",\n            ],\n',
    )
    replace_once(
        ledger_test,
        '                "routes-v5-publication",\n            ],\n',
        '                "routes-v5-publication",\n                "routes-v5-publication-product",\n                "webmcp-reader-publication",\n            ],\n',
    )
    replace_once(
        ledger_test,
        '            "artifacts/lifecycle/004-routes-v5-publication-product",\n',
        '            "artifacts/lifecycle/006-webmcp-reader-publication-product",\n',
    )
    replace_once(
        ledger_test,
        '            "c3ba91ed78fc90f780213b443182b17c38316d77d92f0151fb3d00392e77d9f1",\n',
        '            "2b434f5636675eeacc0d6c4a9676f68a64c953abfada439b1306449ed31ea2a1",\n',
    )

    translation_test = site / "tests/test_site_owned_translations.py"
    replace_once(
        translation_test,
        '            records = publish_translations(\n                {"site": (site_root, documents, assets)},\n                included_pages,\n                docs_root,\n                skip_stale=True,\n            )\n\n            self.assertEqual(len(records), 3)\n',
        '            manifest = load_translation_manifest(\n                site_root / "translations" / "manifest.json",\n                "site translation manifest",\n                publication_root=site_root,\n            )\n            current_before_mutation = sum(\n                entry.is_current for entry in manifest.for_surface("reader")\n            )\n            records = publish_translations(\n                {"site": (site_root, documents, assets)},\n                included_pages,\n                docs_root,\n                skip_stale=True,\n            )\n\n            self.assertEqual(len(records), current_before_mutation - 1)\n',
    )

    run(
        "python",
        str(site / "scripts/generate_agent_bootstrap.py"),
        "--site-root",
        str(site),
        "--composition-root",
        str(composition),
        "--policy-root",
        str(policy),
        "--write",
    )

    manifest_path = site / "translations/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["translations"]:
        canonical = site / entry["canonical"]
        entry["canonical_blob_sha"] = run("git", "hash-object", str(canonical), cwd=site)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    run(
        "python",
        "-m",
        "unittest",
        "tests.test_agent_bootstrap_manifest",
        "tests.test_ledger_overview",
        "tests.test_site_owned_translations",
        cwd=site,
    )

    (site / ".github/workflows/webmcp-s1-remediation.yml").unlink()
    (site / ".github/scripts/webmcp_s1_remediate.py").unlink()

    expected = {
        ".github/scripts/webmcp_s1_remediate.py",
        ".github/workflows/webmcp-s1-remediation.yml",
        "agent.json",
        "assets/agent.json",
        "docs/lifecycle.md",
        "tests/test_ledger_overview.py",
        "tests/test_site_owned_translations.py",
        "translations/ja/docs/capabilities.md",
        "translations/ja/docs/lifecycle.md",
        "translations/manifest.json",
    }
    actual = set(filter(None, run("git", "status", "--short", cwd=site).splitlines()))
    paths = {line[3:] for line in actual}
    if paths != expected:
        raise SystemExit(f"unexpected final remediation paths: {sorted(paths)!r}")

    run("git", "config", "user.name", "webmcp-s1-remediation", cwd=site)
    run("git", "config", "user.email", "webmcp-s1-remediation@users.noreply.github.com", cwd=site)
    run("git", "add", "-A", cwd=site)
    run("git", "commit", "-m", "Repair S1 publication projections and regressions", cwd=site)
    run("git", "push", "origin", "HEAD:webmcp/s1-reader-docs", cwd=site)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
