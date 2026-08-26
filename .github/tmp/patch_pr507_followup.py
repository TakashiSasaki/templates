from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path('.').resolve()


def replace_exact(path: str, old: str, new: str, count: int = 1) -> None:
    file_path = ROOT / path
    text = file_path.read_text(encoding='utf-8')
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f'{path}: expected {count} occurrence(s), found {actual}: {old!r}')
    file_path.write_text(text.replace(old, new), encoding='utf-8')


# Dependency-closure expectation migrations.
replace_exact(
    'tests/test_production_catalog.py',
    '            ["capability.cli", "capability.runtime"],\n',
    '            [\n                "capability.cli",\n                "capability.runtime",\n                "lifecycle.contract-evolution",\n                "lifecycle.implementation-evidence",\n            ],\n',
)
replace_exact(
    'tests/test_composer_public_lifecycle_acceptance.py',
    '                ["capability.cli", "capability.runtime"],\n',
    '                [\n                    "capability.cli",\n                    "capability.runtime",\n                    "lifecycle.contract-evolution",\n                    "lifecycle.implementation-evidence",\n                ],\n',
)
replace_exact(
    'tests/test_composer_upgrade.py',
    '                ["capability.cli", "capability.runtime"],\n',
    '                [\n                    "capability.cli",\n                    "capability.runtime",\n                    "lifecycle.contract-evolution",\n                    "lifecycle.implementation-evidence",\n                ],\n',
    count=2,
)
replace_exact(
    'tests/test_composition_lock_v2.py',
    '                    "exclude": ["lifecycle.release-evidence", "lifecycle.contract-evolution"],\n',
    '                    "exclude": ["lifecycle.release-evidence"],\n',
)
replace_exact(
    'tests/test_composition_lock_v2.py',
    '                    "exclude": ["lifecycle.contract-evolution", "lifecycle.release-evidence"],\n',
    '                    "exclude": ["lifecycle.release-evidence"],\n',
)

post_apply = ROOT / 'tests/test_composer_post_apply_guidance.py'
text = post_apply.read_text(encoding='utf-8')
old_extras = '                ["CLI_INTERFACE.md", "RUNTIME.md"],\n'
if text.count(old_extras) != 3:
    raise SystemExit(f'post-apply extras count changed: {text.count(old_extras)}')
new_extras = (
    '                [\n'
    '                    "CLI_INTERFACE.md",\n'
    '                    "RUNTIME.md",\n'
    '                    "contracts/cli-interface.json",\n'
    '                    "contracts/implementation-evidence.json",\n'
    '                ],\n'
)
post_apply.write_text(text.replace(old_extras, new_extras), encoding='utf-8')

# Walkthrough code and guidance, English and Japanese.
for path in (
    'docs/guides/webapp-product-walkthrough.md',
    'translations/ja/docs/guides/webapp-product-walkthrough.md',
):
    replace_exact(
        path,
        '    parser = argparse.ArgumentParser()\n    parser.add_argument("--database", required=True)\n',
        '    parser = argparse.ArgumentParser()\n    parser.add_argument("--version", action="version", version="Task Ledger 1.0")\n    parser.add_argument("--database", required=True)\n',
    )
    replace_exact(
        path,
        '    if args.command == "export":\n        print(json.dumps(list_tasks(args.database), ensure_ascii=False, indent=2))\n        return 0\n',
        '    if args.command == "export":\n        print(\n            json.dumps(\n                {"contractVersion": "1", "tasks": list_tasks(args.database)},\n                ensure_ascii=False,\n                indent=2,\n            )\n        )\n        return 0\n',
    )
    replace_exact(
        path,
        '        self.assertEqual(json.loads(result.stdout)[0]["title"], "export me")\n',
        '        payload = json.loads(result.stdout)\n        self.assertEqual(payload["contractVersion"], "1")\n        self.assertEqual(payload["tasks"][0]["title"], "export me")\n\n        help_result = subprocess.run(\n            [sys.executable, "-m", "task_ledger.cli", "--database", self.database, "--help"],\n            text=True,\n            capture_output=True,\n            check=False,\n        )\n        self.assertEqual(help_result.returncode, 0, help_result.stderr)\n        self.assertIn("export", help_result.stdout)\n\n        version_result = subprocess.run(\n            [sys.executable, "-m", "task_ledger.cli", "--database", self.database, "--version"],\n            text=True,\n            capture_output=True,\n            check=False,\n        )\n        self.assertEqual(version_result.returncode, 0, version_result.stderr)\n        self.assertEqual(version_result.stdout.strip(), "Task Ledger 1.0")\n\n        invalid = subprocess.run(\n            [\n                sys.executable,\n                "-m",\n                "task_ledger.cli",\n                "--database",\n                self.database,\n                "list",\n                "--status",\n                "invalid",\n            ],\n            text=True,\n            capture_output=True,\n            check=False,\n        )\n        self.assertEqual(invalid.returncode, 2)\n        self.assertIn("invalid choice", invalid.stderr)\n',
    )

# English walkthrough ownership and machine-readable CLI contract guidance.
replace_exact(
    'docs/guides/webapp-product-walkthrough.md',
    '| `contracts/implementation-evidence.json` | `seed` | **Edit later, after real proofs exist.** It initially remains in `template` mode. |\n',
    '| `contracts/cli-interface.json` | `seed` | **Edit it when the selected CLI becomes a product claim.** Keep it in `template` mode until the caller-visible CLI and executable proof exist. |\n| `contracts/implementation-evidence.json` | `seed` | **Edit later, after real proofs exist.** It initially remains in `template` mode. |\n',
)
replace_exact(
    'docs/guides/webapp-product-walkthrough.md',
    'Document stdout/stderr, exit status, invalid arguments, persistence-target selection, and whether CLI operations have semantics equivalent to corresponding API operations.\n',
    '''Document stdout/stderr, exit status, invalid arguments, persistence-target selection, and whether CLI operations have semantics equivalent to corresponding API operations.\n\nBecause `capability.cli` is selected, also replace the editable machine seed `contracts/cli-interface.json` with the caller-visible product contract after the implementation exists:\n\n```json\n{\n  "$schema": "../schemas/cli-interface.schema.json",\n  "schemaVersion": 1,\n  "mode": "product",\n  "entrypoints": [\n    {\n      "id": "task-ledger",\n      "command": ["python", "-m", "task_ledger.cli", "--database", "task-ledger.db"],\n      "workingDirectory": ".",\n      "helpArguments": ["--help"],\n      "versionArguments": ["--version"],\n      "structuredOutput": {\n        "arguments": ["export"],\n        "format": "json",\n        "contractVersionField": "contractVersion"\n      },\n      "exitCodes": {\n        "success": 0,\n        "negativeResult": 1,\n        "invalidInput": 2,\n        "unavailable": 3,\n        "refused": 4,\n        "internalFailure": 5,\n        "additionalInputRequired": 6\n      }\n    }\n  ]\n}\n```\n\nDo not switch this contract to `product` merely because the CLI source file exists. The `--help`, `--version`, structured `export`, and invalid-input paths below are executed by the product verifier, and Section 15 links those executable checks to a `cli_interface/entrypoint/task-ledger` evidence record.\n''',
)
replace_exact(
    'docs/guides/webapp-product-walkthrough.md',
    'The consumer-owned unit/integration checks pass and the command exits successfully. The tests exercise SQLite persistence across independent connections, filtering/update behavior, CLI export, an independently reachable JSON API, health, and a negative invalid-filter case.\n',
    'The consumer-owned unit/integration checks pass and the command exits successfully. The tests exercise SQLite persistence across independent connections, filtering/update behavior, CLI help/version/structured export plus an invalid-argument exit-2 path, an independently reachable JSON API, health, and a negative invalid-filter case.\n',
)
replace_exact(
    'docs/guides/webapp-product-walkthrough.md',
    'For the generated `viewports/base` and `input-capability/keyboard` records, use `tests/test_task_ledger_browser.py` as the positive and negative proof locator, `end-to-end-test` as the proof kind, and `verify-product` as the command ID. The expected results must describe the corresponding successful interaction and rejected/absent invalid behavior rather than merely saying that the file exists.\n',
    '''For the generated `viewports/base` and `input-capability/keyboard` records, use `tests/test_task_ledger_browser.py` as the positive and negative proof locator, `end-to-end-test` as the proof kind, and `verify-product` as the command ID. The expected results must describe the corresponding successful interaction and rejected/absent invalid behavior rather than merely saying that the file exists.\n\nBecause `capability.cli` is selected, add one further record whose target is `contract-item / cli_interface / entrypoint / task-ledger`. Its implementation boundary is `task_ledger/cli.py`; its positive and negative proof locator is `tests/test_task_ledger.py`; and its proof kind is `integration-test`. Link that record from a stable CLI requirement whose `requiredPositiveProofKinds` contains `integration-test`. The positive path covers help/version/structured export, while the negative path covers the invalid-argument exit code. A selected CLI contract left in `template` mode, or a CLI record backed only by source inspection/unit-only proof, must keep Composition validation invalid.\n''',
)
replace_exact(
    'docs/guides/webapp-product-walkthrough.md',
    '- implementation evidence is in `product` mode with complete current-target coverage;\n',
    '- implementation evidence is in `product` mode with complete current-target coverage;\n- when `capability.cli` is selected, `contracts/cli-interface.json` is in truthful `product` mode and every declared CLI entrypoint has executable positive/negative evidence;\n',
)

# Japanese ownership and CLI product contract guidance.
replace_exact(
    'translations/ja/docs/guides/webapp-product-walkthrough.md',
    '| `contracts/implementation-evidence.json` | `seed` | **real proof ができてから編集する。** |\n',
    '| `contracts/cli-interface.json` | `seed` | **selected CLI を product claim にするとき編集する。** caller-visible CLI と executable proof が揃うまでは `template` mode を維持する。 |\n| `contracts/implementation-evidence.json` | `seed` | **real proof ができてから編集する。** |\n',
)
replace_exact(
    'translations/ja/docs/guides/webapp-product-walkthrough.md',
    '```sh\npython -m task_ledger.cli --database task-ledger.db list --status all\npython -m task_ledger.cli --database task-ledger.db export\n```\n\n## 12. Minimal consumer-owned implementation と tests を作る\n',
    '''```sh\npython -m task_ledger.cli --database task-ledger.db list --status all\npython -m task_ledger.cli --database task-ledger.db export\n```\n\n`capability.cli` を選択しているため、実装後には editable seed `contracts/cli-interface.json` も caller-visible product contract にします。\n\n```json\n{\n  "$schema": "../schemas/cli-interface.schema.json",\n  "schemaVersion": 1,\n  "mode": "product",\n  "entrypoints": [\n    {\n      "id": "task-ledger",\n      "command": ["python", "-m", "task_ledger.cli", "--database", "task-ledger.db"],\n      "workingDirectory": ".",\n      "helpArguments": ["--help"],\n      "versionArguments": ["--version"],\n      "structuredOutput": {\n        "arguments": ["export"],\n        "format": "json",\n        "contractVersionField": "contractVersion"\n      },\n      "exitCodes": {\n        "success": 0,\n        "negativeResult": 1,\n        "invalidInput": 2,\n        "unavailable": 3,\n        "refused": 4,\n        "internalFailure": 5,\n        "additionalInputRequired": 6\n      }\n    }\n  ]\n}\n```\n\nsource file が存在するだけで `product` にしてはいけません。下の product verifier が `--help`、`--version`、structured `export`、invalid-input path を実行し、Section 15 で `cli_interface/entrypoint/task-ledger` evidence record に接続します。\n\n## 12. Minimal consumer-owned implementation と tests を作る\n''',
)
# Add Japanese evidence guidance near the existing browser-target paragraph if present.
replace_exact(
    'translations/ja/docs/guides/webapp-product-walkthrough.md',
    'generated `viewports/base` と `input-capability/keyboard` record では、positive / negative proof locator に `tests/test_task_ledger_browser.py`、proof kind に `end-to-end-test`、command ID に `verify-product` を使用します。expected result は file existence ではなく、対応する成功 interaction と rejected/absent invalid behavior を記述します。\n',
    'generated `viewports/base` と `input-capability/keyboard` record では、positive / negative proof locator に `tests/test_task_ledger_browser.py`、proof kind に `end-to-end-test`、command ID に `verify-product` を使用します。expected result は file existence ではなく、対応する成功 interaction と rejected/absent invalid behavior を記述します。\n\n`capability.cli` を選択しているため、さらに `contract-item / cli_interface / entrypoint / task-ledger` target の record を1件追加します。implementation boundary は `task_ledger/cli.py`、positive / negative proof locator は `tests/test_task_ledger.py`、proof kind は `integration-test` とし、`requiredPositiveProofKinds` に `integration-test` を含む stable CLI requirement から link します。positive path は help/version/structured export、negative path は invalid argument の exit code を実行します。CLI contract が `template` のまま、または source inspection / unit-only proof しかない状態を valid product completion としてはいけません。\n',
)

# Task Ledger acceptance: productize selected CLI contract and evidence.
acceptance = ROOT / 'tests/test_task_ledger_walkthrough_browser_acceptance.py'
text = acceptance.read_text(encoding='utf-8')
needle = '    def expected_targets(self, target: Path) -> list[dict[str, str]]:\n'
if text.count(needle) != 1:
    raise SystemExit('Task Ledger expected_targets insertion point changed')
method = '''    def productize_cli_contract(self, target: Path) -> None:\n        self.write_json(\n            target / "contracts" / "cli-interface.json",\n            {\n                "$schema": "../schemas/cli-interface.schema.json",\n                "schemaVersion": 1,\n                "mode": "product",\n                "entrypoints": [\n                    {\n                        "id": "task-ledger",\n                        "command": [\n                            "python",\n                            "-m",\n                            "task_ledger.cli",\n                            "--database",\n                            "task-ledger.db",\n                        ],\n                        "workingDirectory": ".",\n                        "helpArguments": ["--help"],\n                        "versionArguments": ["--version"],\n                        "structuredOutput": {\n                            "arguments": ["export"],\n                            "format": "json",\n                            "contractVersionField": "contractVersion",\n                        },\n                        "exitCodes": {\n                            "success": 0,\n                            "negativeResult": 1,\n                            "invalidInput": 2,\n                            "unavailable": 3,\n                            "refused": 4,\n                            "internalFailure": 5,\n                            "additionalInputRequired": 6,\n                        },\n                    }\n                ],\n            },\n        )\n\n'''
text = text.replace(needle, method + needle)
old = '        self.write_json(\n            target / "contracts" / "implementation-evidence.json",\n'
if text.count(old) != 1:
    raise SystemExit('Task Ledger evidence write insertion point changed')
addition = '''        cli_record_id = "task-ledger-cli"\n        records.append(\n            {\n                "id": cli_record_id,\n                "target": {\n                    "kind": "contract-item",\n                    "contractId": "cli_interface",\n                    "itemKind": "entrypoint",\n                    "itemId": "task-ledger",\n                },\n                "implementationBoundary": {\n                    "status": "verified",\n                    "description": "Task Ledger exposes the selected packaged CLI entrypoint.",\n                    "locator": "task_ledger/cli.py",\n                },\n                "positiveEvidence": [\n                    {\n                        "id": "task-ledger-cli-positive",\n                        "status": "verified",\n                        "kind": "integration-test",\n                        "description": "CLI help, version, and structured export execute successfully.",\n                        "locator": "tests/test_task_ledger.py",\n                        "commandId": "verify-product",\n                        "expectedResult": "Help/version succeed and export emits contractVersion 1 JSON.",\n                    }\n                ],\n                "negativeEvidence": [\n                    {\n                        "id": "task-ledger-cli-negative",\n                        "status": "verified",\n                        "kind": "integration-test",\n                        "description": "CLI rejects an invalid status argument through argparse.",\n                        "locator": "tests/test_task_ledger.py",\n                        "commandId": "verify-product",\n                        "expectedResult": "Invalid --status exits with code 2 and a diagnostic.",\n                    }\n                ],\n                "releaseGateIds": ["product-verification"],\n            }\n        )\n        requirements.append(\n            {\n                "id": "REQ-TASK-LEDGER-CLI",\n                "description": "Task Ledger exposes a versioned structured CLI with executable positive and negative behavior.",\n                "recordIds": [cli_record_id],\n                "requiredPositiveProofKinds": ["integration-test"],\n            }\n        )\n\n'''
text = text.replace(old, addition + old)
old_call = '            self.productize_evidence(target)\n'
if text.count(old_call) != 1:
    raise SystemExit('Task Ledger productize call changed')
text = text.replace(old_call, '            self.productize_cli_contract(target)\n            self.productize_evidence(target)\n')
acceptance.write_text(text, encoding='utf-8')

# Translation binding for canonical walkthrough after edits.
manifest_path = ROOT / 'translations' / 'manifest.json'
manifest_text = manifest_path.read_text(encoding='utf-8')
new_blob = subprocess.check_output(
    ['git', 'hash-object', 'docs/guides/webapp-product-walkthrough.md'], text=True
).strip()
old_blob = 'c693405ae87f40f84305a6aa7767a0595839d90a'
if manifest_text.count(old_blob) != 1:
    raise SystemExit(f'walkthrough manifest binding count changed: {manifest_text.count(old_blob)}')
manifest_path.write_text(manifest_text.replace(old_blob, new_blob), encoding='utf-8')

print('PR507 follow-up patch applied')
