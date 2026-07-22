---
description: 外部archive、historical source、vendor bundle、生成物などを安全に受領・検証・stageする共有規約と運用境界を説明します。
---

# 外部artifact受領規約プロファイル

`external-artifact-intake` profileは、別repository、外部生成工程、配布archive、historical snapshot、vendor bundleなどからartifactを受け取り、destination repositoryへ導入する作業に適用します。

このprofileは`core`へ暗黙には含めません。外部artifactを扱う製品repositoryが`.agent-policy.yml`で明示的に選択します。

```yaml
profiles:
  - core
  - external-artifact-intake
```

## 収録する規則

| 規則ID | 要点 |
|---|---|
| `artifacts.distinguish-provenance-integrity` | provenance claim、transfer integrity、source authenticity、source-set completenessを別の主張として扱う |
| `artifacts.validate-before-use` | metadataとschemaを先に検証し、その後にpath、symlink、file type、size、digestを検査する |
| `artifacts.apply-declared-intent-only` | artifactごとに宣言された利用目的を超えてinstall、activate、再構成しない |
| `artifacts.separate-staging-adaptation-activation` | exact-byte staging、destination adaptation、runtime activationを別の変更として扱う |
| `artifacts.isolate-transport-material` | archive、sidecar、展開tree、reportを通常の製品diffへ混入させない |
| `artifacts.minimize-dependency-closure` | source側manifestをdestinationの正本にせず、必要最小限のdependencyだけを追加する |

## 証拠の意味を分離する

外部artifactの検証では、似ているが異なる主張を混同しないことが重要です。

```text
repository、revision、URLの記録
  → provenance claim

archiveのSHA-256一致
  → 確認したarchive bytesのtransfer integrity

source systemのblob IDまたは署名との一致
  → そのsource objectとのbyte identityまたはauthenticity

manifestへ列挙されたfileの検証
  → 列挙された集合の内部整合性
```

これらのいずれも、それ単独ではsource repository全体が完全に収録されていることを証明しません。限定的なpacket、reference bundle、選択的なrestore setは、限定的であることを明示して扱います。

## 検証順序

Artifact-controlled pathを使用する前に、宣言構造を検証します。標準的な順序は次です。

1. source identity、destination baseline、expected digest、declared intentを確認する。
2. archiveをrepository外の一時領域へ取得する。
3. transfer digestを検証する。
4. 展開前にarchive entryを検査する。
5. 一時領域へ展開する。
6. repository-authoritativeなschema validatorとoperational validatorを実行する。
7. containment、regular file、symlink、size、digest、duplicate destinationを検査する。
8. declared intentが許可するentryだけを適用する。
9. destination bytesとdependency diffを検証する。
10. repositoryの必須検証を実行し、transport materialがfinal diffに残っていないことを確認する。

Producerが添付したvalidation reportは有用なevidenceですが、destination repositoryのauthoritative validatorを実行した結果の代替にはなりません。

## Staging、adaptation、activation

Exact historical sourceや署名済みartifactをstageする場合、byte-for-byte一致を確認するまでsourceを編集しません。Import path変更、formatting、compatibility wrapper、dependency追加、route接続、runtime activationは、stagingとは異なる変更です。

```text
transfer validation
  → exact-byte staging
  → destination adaptation
  → runtime activation
  → publishまたはdeploy
```

各段階は独立したscopeとevidenceを持ちます。前段階のPASSだけで後段階を暗黙に許可しません。

## Operational skills

このprofileと組み合わせて、必要なrepositoryだけが次のskillを選択できます。

```yaml
skills:
  enabled:
    - validate-agent-policy
    - intake-validated-artifact
    - audit-frozen-change
```

`intake-validated-artifact`はdownload、archive inspection、authoritative validation、declared-intent application、dependency review、transport cleanupまでの標準手順を提供します。

`audit-frozen-change`は、合意済みacceptance baselineに対してregressionとevidenceを評価し、audit中に新しいgateを発明しないための停止条件を提供します。

## 製品固有規約との境界

次は共有profileではなく、製品repositoryのproject policy、schema、validator、test、CIで定義します。

- manifestの具体的fieldとversion
- dispositionまたはactionの具体的enum
- 許可されるsource repositoryとdestination path
- baseline revisionの取得方法
- archive format、size上限、署名方式
- file mapping、dependency policy、activation gate
- database、runtime、migrationに関する製品固有の禁止事項
- acceptance reportの具体的format

自然言語の共有規約だけでartifact contractを代替せず、検証可能な部分はdestination repositoryのvalidatorとCIで強制してください。
