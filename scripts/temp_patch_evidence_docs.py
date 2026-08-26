from __future__ import annotations

import json
import subprocess
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    file.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "docs/guides/webapp-product-walkthrough.md",
    """## 15. Switch implementation evidence to product mode only after proof exists

The initial `contracts/implementation-evidence.json` is intentionally in `template` mode with no product implementation claim. Change it to `product` mode only after the implementation, `./scripts/verify.sh`, and referenced proof locations really exist.

The unit/integration portion of the Section 12 verifier is **not** browser-level proof by itself. The downloaded `tests/test_task_ledger_browser.py` adds real positive and negative `end-to-end-test` paths for the viewport and keyboard targets. If you skip that script or it does not run successfully in a real browser, keep implementation evidence in `template` mode. Do not relabel source inspection, HTTP reachability, or unit tests as browser proof.
""",
    """## 15. Make incomplete product evidence explicit

The initial `contracts/implementation-evidence.json` is intentionally in `template` mode with no product implementation claim. Once Task Ledger has concrete caller-visible requirements, implemented boundaries, and real proof definitions, switch to `product` mode and enumerate every requirement with a stable requirement ID, linked `recordIds`, and a non-empty `requiredPositiveProofKinds` declaration. Do not add a synthetic catch-all requirement merely to satisfy the schema.

The unit/integration portion of the Section 12 verifier is **not** browser-level proof by itself. The downloaded `tests/test_task_ledger_browser.py` defines real positive and negative `end-to-end-test` paths for the viewport and keyboard targets. If that proof exists but Chrome/ChromeDriver or another required execution environment is temporarily unavailable, keep the product claim machine-visible and mark the affected proof `deferred`. A deferred proof may remain structurally valid, but it is unfinished evidence and blocks release readiness. If the proof definition or locator itself does not yet exist, do not fabricate it; remain in `template` mode until the product evidence graph can be stated truthfully.

Do not relabel source inspection, HTTP reachability, or unit tests as browser proof. `requiredPositiveProofKinds` records the minimum acceptable positive proof class for each requirement; for browser interaction use `end-to-end-test` and/or `accessibility-test`, while executable CLI behavior can require `integration-test`.
""",
)

replace_once(
    "docs/guides/webapp-product-walkthrough.md",
    """After every current target—including viewport and keyboard targets—has truthful proof of the required kind, run both verification layers.

**Run**

```sh
./scripts/verify.sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \\
  --repository /absolute/path/to/task-ledger \\
  validate
```

**Expected**

- the authoritative product verification command, including the referenced browser suite, passes; and
- Composition validation returns `status: "valid"` with implementation evidence executed rather than template-deferred.

If the real-browser script was omitted, skipped, or unable to start Chrome/ChromeDriver, this stronger product-mode result is not claimed; keep the evidence document in `template` mode.

**What this means**

Task Ledger now has both a product-behavior claim backed by consumer tests and a valid closed Composition contract/evidence relationship. This is the point at which “valid scaffold” and “implemented, product-tested application” have both been satisfied rather than confused.
""",
    """Run the structural validation whenever product evidence changes. Run the stricter release-readiness check before claiming that the evidence can approve a release.

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \\
  --repository /absolute/path/to/task-ledger \\
  validate
python .template-composition/validators/validate_implementation_evidence.py \\
  . --release-readiness
```

When every required proof is available, also run the authoritative product verifier:

```sh
./scripts/verify.sh
```

**Expected**

- Composition validation returns `status: "valid"` with implementation evidence executed rather than template-deferred;
- the release-readiness command exits successfully only when every required proof, including browser-sensitive proof, is `verified`; and
- the authoritative product verification command passes before the implemented-product milestone is claimed.

If Chrome/ChromeDriver is unavailable, a truthful `product` document may still contain `deferred` browser proof. In that state the worklist must continue to show the remaining evidence, release readiness must remain `NOT READY`, and the implemented-product/release-ready milestone must not be claimed.

**What this means**

Task Ledger can represent both complete and incomplete product evidence without confusing either state with a valid scaffold. `product` mode means that concrete product requirements and implementation claims exist; release readiness is the stronger statement that every required proof has actually been verified.
""",
)

replace_once(
    "docs/guides/webapp-product-walkthrough.md",
    """- implementation evidence is in `product` mode with complete current-target coverage and real positive/negative proofs, including browser-level proof for browser-sensitive targets;
- Composition validation passes with implementation evidence executed rather than template-deferred; and
""",
    """- implementation evidence is in `product` mode with complete current-target coverage;
- every caller-visible product requirement has a stable requirement ID, linked records, and a non-empty `requiredPositiveProofKinds` declaration;
- real positive/negative proofs satisfy those declared proof kinds, including browser-level proof for browser-sensitive requirements, with no required proof left `deferred`;
- Composition validation passes with implementation evidence executed rather than template-deferred;
- release-readiness validation passes; and
""",
)

replace_once(
    "translations/ja/docs/guides/webapp-product-walkthrough.md",
    """## 15. Proof が存在してから implementation evidence を product mode にする

initial `contracts/implementation-evidence.json` は `template` mode です。implementation、`./scripts/verify.sh`、proof location が実在してから `product` mode にします。

Section 12 verifierのunit/integration部分だけではbrowser-level proofになりません。downloadした `tests/test_task_ledger_browser.py` が、viewport/keyboard targetに対する実ブラウザのpositive/negative `end-to-end-test` pathを追加します。このscriptを省略した場合、または実ブラウザで正常実行できない場合は、implementation evidenceを `template` modeに保ちます。source inspection、HTTP reachability、unit testをbrowser proofとして再分類してはいけません。
""",
    """## 15. 未完了の product evidence を明示的に表現する

initial `contracts/implementation-evidence.json` は product implementation claim を持たない `template` mode です。Task Ledger に具体的な caller-visible requirement、実装済み boundary、実在する proof 定義が揃ったら `product` mode に切り替え、すべての requirement に stable requirement ID、対応する `recordIds`、non-empty な `requiredPositiveProofKinds` を宣言します。schema を満たすだけの synthetic catch-all requirement を追加してはいけません。

Section 12 verifier の unit/integration 部分だけでは browser-level proof になりません。download した `tests/test_task_ledger_browser.py` は viewport/keyboard target に対する実ブラウザの positive/negative `end-to-end-test` path を定義します。その proof 自体は存在するものの Chrome/ChromeDriver など必要な実行環境が一時的に利用できない場合は、product claim を machine-visible なまま維持し、該当 proof を `deferred` にします。`deferred` は構造的には有効であり得ますが未完了 evidence であり、release readiness を block します。proof 定義や locator 自体がまだ存在しない場合は、それを捏造せず、evidence graph を truthful に記述できるまで `template` mode に留まります。

source inspection、HTTP reachability、unit test を browser proof として再分類してはいけません。`requiredPositiveProofKinds` は各 requirement を満たすための最低限の positive proof class を記録します。browser interaction には `end-to-end-test` や `accessibility-test`、実行可能 CLI behavior には `integration-test` を指定できます。
""",
)

replace_once(
    "translations/ja/docs/guides/webapp-product-walkthrough.md",
    """viewport と keyboard を含むすべての current target に、要求された kind の truthful proof が存在してから、両方の verification layer を実行します。

```sh
./scripts/verify.sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \\
  --repository /absolute/path/to/task-ledger \\
  validate
```

browser suite を含む authoritative product verification が pass し、Composition validation が `status: "valid"`、implementation evidence が template-deferred ではなく executed されることを確認します。

実ブラウザscriptを省略、skip、またはChrome/ChromeDriver起動失敗のままにした場合、この強いproduct-mode resultをclaimしません。その場合はevidence documentを `template` modeに保ちます。
""",
    """product evidence を変更するたびに structural validation を実行し、その evidence が release を承認できると claim する前に、より厳しい release-readiness check を実行します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \\
  --repository /absolute/path/to/task-ledger \\
  validate
python .template-composition/validators/validate_implementation_evidence.py \\
  . --release-readiness
```

必要な proof がすべて利用可能な場合は authoritative product verifier も実行します。

```sh
./scripts/verify.sh
```

Composition validation が `status: "valid"` で implementation evidence が template-deferred ではなく実行されること、release-readiness command が browser-sensitive proof を含むすべての required proof が `verified` の場合にのみ成功すること、そして implemented-product milestone を claim する前に authoritative product verification が pass することを確認します。

Chrome/ChromeDriver が利用できない場合でも、truthful な `product` document に browser proof を `deferred` として保持できます。その状態では worklist に残作業を表示し続け、release readiness は `NOT READY` のままとし、implemented-product / release-ready milestone を claim してはいけません。
""",
)

replace_once(
    "translations/ja/docs/guides/webapp-product-walkthrough.md",
    """**Implemented-product milestone:** truthful consumer contracts、product source/tests、browser-sensitive target の browser-level proof を含む passing product verifier、complete product-mode implementation evidence、executed implementation-evidence を含む valid Composition validation、必要なら独立した valid Policy state。
""",
    """**Implemented-product milestone:** truthful consumer contracts、product source/tests、complete current-target coverage、stable requirement ID と linked record/non-empty `requiredPositiveProofKinds` を持つすべての caller-visible requirement、宣言した kind を満たす real positive/negative proof（required proof に `deferred` を残さない）、passing product verifier、executed implementation-evidence を含む valid Composition validation、passing release-readiness validation、必要なら独立した valid Policy state。
""",
)

replace_once(
    "docs/release-guide.md",
    """The scaffold is non-destructive. Use its records to populate product-mode implementation evidence with:

- the implementation boundary for each required target;
- positive evidence;
- negative evidence where required;
- the authoritative proof `commandId`; and
- the release gate IDs that consume that proof.

The human-readable `command` stored in implementation evidence identifies the proof for review and digest binding. It is not parsed as shell input by the release producer.

Run the implementation-evidence and Webapp evidence validators while filling these records. Product evidence should fail closed until every required target and release gate is covered.
""",
    """The scaffold is non-destructive. Use its records to populate product-mode implementation evidence with:

- the implementation boundary for each required target;
- an explicit stable requirement ID for every caller-visible product requirement;
- each requirement's linked `recordIds` and non-empty `requiredPositiveProofKinds` declaration;
- positive evidence;
- negative evidence where required;
- the authoritative proof `commandId`; and
- the release gate IDs that consume that proof.

The human-readable `command` stored in implementation evidence identifies the proof for review and digest binding. It is not parsed as shell input by the release producer. If a required execution environment is temporarily unavailable after the proof definition and locator exist, keep the product requirement visible and mark that proof `deferred`; do not substitute weaker static evidence. Deferred evidence may remain structurally valid, but release readiness and release production reject it.

Run the implementation-evidence and Webapp evidence validators while filling these records, and run `python .template-composition/validators/validate_implementation_evidence.py . --release-readiness` before release production. Product evidence should fail closed until every required target, requirement-to-proof-kind edge, and release gate is covered; release readiness should fail until every required proof is `verified`.
""",
)

replace_once(
    "translations/ja/docs/release-guide.md",
    """scaffold は non-destructive です。生成された record を使用し、product-mode implementation evidence に次を記録します。

- 必要な各 target の implementation boundary。
- positive evidence。
- 必要な場合の negative evidence。
- authoritative proof の `commandId`。
- その proof を利用する release gate ID。

implementation evidence に保存する human-readable な `command` は、review と digest binding のために proof を識別します。release producer がこれを shell input として parse することはありません。

record を埋める間も implementation-evidence validator と Webapp evidence validator を実行してください。必要な target と release gate がすべて cover されるまで product evidence は fail closed であるべきです。
""",
    """scaffold は non-destructive です。生成された record を使用し、product-mode implementation evidence に次を記録します。

- 必要な各 target の implementation boundary。
- すべての caller-visible product requirement に対する明示的で stable な requirement ID。
- 各 requirement の linked `recordIds` と non-empty な `requiredPositiveProofKinds` 宣言。
- positive evidence。
- 必要な場合の negative evidence。
- authoritative proof の `commandId`。
- その proof を利用する release gate ID。

implementation evidence に保存する human-readable な `command` は、review と digest binding のために proof を識別します。release producer がこれを shell input として parse することはありません。proof 定義と locator が存在した後で必要な実行環境が一時的に利用できない場合は、product requirement を machine-visible なまま維持し、その proof を `deferred` にします。より弱い static evidence で代用してはいけません。deferred evidence は構造的には有効であり得ますが、release readiness と release production は拒否します。

record を埋める間も implementation-evidence validator と Webapp evidence validator を実行し、release production 前には `python .template-composition/validators/validate_implementation_evidence.py . --release-readiness` を実行してください。必要な target、requirement-to-proof-kind edge、release gate がすべて cover されるまで product evidence は fail closed であり、必要な proof がすべて `verified` になるまで release readiness は fail すべきです。
""",
)

manifest_path = Path("translations/manifest.json")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
for canonical in (
    "docs/guides/webapp-product-walkthrough.md",
    "docs/release-guide.md",
):
    sha = subprocess.check_output(["git", "hash-object", canonical], text=True).strip()
    for entry in manifest["translations"]:
        if entry["canonical"] == canonical:
            entry["canonical_blob_sha"] = sha
            break
    else:
        raise SystemExit(f"missing translation manifest entry: {canonical}")
manifest_path.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
