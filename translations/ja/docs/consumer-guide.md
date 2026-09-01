# Composition の利用方法

> **参考訳（非正本）:** この文書は英語版 `docs/consumer-guide.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

このガイドは、Composition を使用して具体的な Agent Skill、Website、または Web application repository を作成・保守する consumer 向けです。通常の consumer はインストール済み Composition skill runner を使用し、その下では Composer が引き続き semantic authority です。

ここで **Composition authority 保守者** とは、`TakashiSasaki/templates` の `composition` authority 自体を変更・保守する人を指します。consumer repository の保守者とは区別します。

Composer の正確な options、plan fields、ownership definitions、diagnostic codes については [Composer reference](reference/composer.md) を参照してください。

## 操作を選ぶ

| 目的 | 操作 |
| --- | --- |
| まだ Composition-managed でない repository を作成する | `initial` |
| 記録済み intent を変えず、より新しい descendant Composition revision へ進める | `update` |
| recipe、component selection、parameters を変更する、または component-version compatibility boundary を越える | `upgrade` |
| 中断された `update` / `upgrade` を再開する | 対応する `apply --mode ...` を再実行する |

`inspect` と `validate` は mode-neutral です。mutation の前に `inspect`、成功した apply の後に `validate` を使用します。

<a id="composition-skill-install"></a>

## Composition skill をインストールして実行する

通常の consumer に必要な local prerequisite は CPython 3.11、3.12、3.13、または 3.14 です。**通常の Composition consumption に Git は不要です。** `TakashiSasaki/templates`、`composition`、`site`、`policy` のいずれも clone せずに利用できます。インストール済み runner は選択された immutable full-SHA Composition revision を HTTPS で取得し、source bootstrap には Python standard library を使用します。

cold execution では、選択された full-SHA source archive を取得するための GitHub network access が必要です。また一致する Python runtime cache が存在しない場合は、設定された Python package source への access が必要です。managed `update` / `upgrade` ではさらに GitHub compare API による old-to-new revision ancestry 検証が必要です。これらの network dependency は fail closed であり、mutable branch への fallback や ancestry の推測は行いません。

sandbox、container、CI worker など、既定 user cache が writable でない環境では runner を最初に呼ぶ前に writable cache root を指定してください。

```sh
export COMPOSITION_RUNTIME_CACHE=/path/to/writable/composition-runtime-cache
export COMPOSITION_VALIDATION_CACHE=/path/to/writable/composition-validation-cache
```

cache は product repository の外側に置きます。`COMPOSITION_RUNTIME_CACHE` に残るのは validation 済み Python runtime state であり、通常の Composition source snapshot は disposable で、そこには保存されません。

通常の consumer は immutable かつ stdlib-only の bootstrap script から公開済み Composition skill をインストールします。installer URL は branch/tag ではなく review 済み installer commit に固定され、downloaded bytes は write / execute の前に公開済み SHA-256 と一致しなければなりません。

```sh
python -I -c '
import hashlib
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

url = "https://raw.githubusercontent.com/TakashiSasaki/templates/5a3cfb200ed68d87da1a8e128b61b40401820347/scripts/install_composition_skill.py"
expected = "114c3375f4edef8aa64f42ab3beeaae246fdf8b960f6eb09868648e6a62cd1ab"
data = urllib.request.urlopen(url, timeout=30).read()
actual = hashlib.sha256(data).hexdigest()
if actual != expected:
    raise SystemExit(f"installer SHA-256 mismatch: expected {expected}, got {actual}")
print(f"Verified Composition installer SHA-256: {actual}")
with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as handle:
    handle.write(data)
    installer = pathlib.Path(handle.name)
try:
    subprocess.run([sys.executable, "-I", str(installer), *sys.argv[1:]], check=True)
finally:
    installer.unlink(missing_ok=True)
' /path/to/agent-skills/composition
```

digest mismatch では installer bytes を書き出す前かつ installer process を起動する前に終了します。出力される verified digest は audit evidence として保存できます。既存 destination にこの Composition skill がある場合は `--replace` を追加できます。`SKILL.md` によって `composition` skill と識別できない directory の replacement は拒否されます。

公開済み immutable identity は役割ごとに分かれています。installer `5a3cfb200ed68d87da1a8e128b61b40401820347` は skill source `8defa866d088de7f8c29bc3a5443dc2df69983dc` をインストールし、その runtime manifest は stable toolchain `199f25731170a6e25d25aa759fa6edc038623f58` を選択します。installer bytes はさらに SHA-256 `114c3375f4edef8aa64f42ab3beeaae246fdf8b960f6eb09868648e6a62cd1ab` に固定されています。これらは `release/composition-installer.json` に記録され、Composition CI が repository history から検証します。mutable branch/tag を installer URL に置き換えず、verified bootstrap を downloaded bytes の direct execution に置き換えないでください。

通常の command shape は次のとおりです。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  COMMAND [COMPOSER OPTIONS]
```

runner が Composer target を所有します。Composer の `--target` を重ねて渡さず、runner の `--repository` を使用してください。

### Doctor

local bootstrap prerequisite や runtime-cache behavior を診断するには read-only `doctor` を使用します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  doctor
```

machine-readable 出力には `doctor --format json` を使用します。doctor は selected immutable revision、対応 CPython、persistent runtime-cache の write/atomic-rename capability を検査します。通常 consumer の Git は `not-required`、source acquisition は `ephemeral` と報告します。doctor は GitHub や package index に接続せず、source/runtime state を acquire しません。したがって `READY` は local bootstrap diagnosis であり、Composition validation の代替でも、後続 cold acquisition の network availability 保証でもありません。

### Initial composition

まだ managed でない repository では、`initial` mode から始めます。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --config /path/to/repository/composition.json --mode initial
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --config /path/to/repository/composition.json --mode initial
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

`plan` が成功したら、その plan を review してから `apply` します。`apply` を省略してはいけません。apply 後の `validate` は resolved component state と material ownership を検証します。

### Update

記録済み intent を維持したままより新しい Composition revision へ進める場合は `update` を使用します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --mode update --revision <new-full-sha>
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode update --revision <new-full-sha>
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

`update` は recorded intent を変更しません。old revision から new revision への ancestry を GitHub compare API で検証し、descendant でない revision は拒否します。

### Upgrade

recipe、component selection、parameter を変更する場合は `upgrade` を使用します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --config /path/to/repository/composition.json --mode upgrade --revision <new-full-sha>
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --config /path/to/repository/composition.json --mode upgrade --revision <new-full-sha>
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

`upgrade` は requested intent を変える mutation です。plan で existing lock、requested configuration、resolved target state の差を review してから apply します。

## Inspect state

`inspect` は repository の現在状態を machine-readable に分類します。代表的な state は次のとおりです。

- `unmanaged`
- `managed`
- `interrupted-transaction`
- `invalid`

mutation 前の `inspect` は prerequisite です。状態が `interrupted-transaction` なら、対応する apply を再実行して recovery を完了します。別 mutation を始めてはいけません。

## Ownership と conflict

Composition は material を次の ownership class に分類します。

- `managed`
- `generated`
- `consumer-owned`

managed/generated material は old-lock digest と一致する場合だけ replace/delete できます。consumer-owned file は Composition が自動上書きしません。conflict は fail closed で停止し、material の所有者と現在 content を確認してから解消します。

## Validation と evidence

`validate` は scaffold validity と selected component contracts を検証します。product completion を意味しません。implementation evidence を持つ artifact では、planning と product の lifecycle state を区別し、required proof が未実行なら release readiness は ready になりません。

## Recovery

transaction が interrupted になった場合、別 mutation を開始せず、同じ apply operation を再実行します。Composer は transaction journal と lock state から recovery path を決定します。手作業で lock や journal を整形して recovery を偽装しないでください。
