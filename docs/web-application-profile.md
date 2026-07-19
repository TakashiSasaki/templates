---
description: Webアプリケーションのインターフェイスサーフェスに適用する共有規約と、製品固有規約との境界を説明します。
---

# Webアプリケーション規約プロファイル

`web-application` profileは、Webアプリケーションが外部へ提示するインターフェイスサーフェスを、利用者、目的、アクセス条件、データ機密性、安定性の異なる契約として扱うための共有規約です。

このprofileは`core`や`security-baseline`へ暗黙には含まれません。Webアプリケーションを持つ製品リポジトリが、`.agent-policy.yml`で明示的に選択します。

```yaml
profiles:
  - core
  - security-baseline
  - web-application
```

## 収録する規則

| 規則ID | 要点 |
|---|---|
| `interfaces.define-surface-boundaries` | サーフェスを利用者、目的、アクセス条件、機密性、安定性で分類し、URL名やディレクトリ名を認可境界にしない |
| `interfaces.isolate-surface-dependencies` | 各サーフェスの初期依存を必要最小限にし、無関係な初期化や障害を波及させない |
| `interfaces.make-navigation-intentional` | canonical route、redirect、alias、deep link、認証復帰、browser navigationを明示的な契約にする |
| `interfaces.model-user-visible-states` | loading、empty、partial、error、offline、retryなどの状態と回復動作を定義する |
| `interfaces.preserve-accessible-interaction` | 非同期更新や画面遷移後もsemantic、keyboard、focus、accessible stateを維持する |
| `interfaces.separate-diagnostics` | 通常利用画面とstatus、developer、administrative diagnosticsを分離する |
| `interfaces.keep-surface-contracts-synchronized` | route、navigation、authorization、documentation、deployment、testを同期して変更する |
| `interfaces.adapt-layout-to-content` | 単一device classの制約を全体へ強制せず、内容と対応viewportに応じて表現を選ぶ |

## 製品固有規約との境界

共有profileは、`public`、`app`、`admin`、`dev`、`api`、`demo`、`test`などの具体的なサーフェス名やURL構造を強制しません。次の事項は製品リポジトリのproject policyまたは機械可読な設定・テストで定義します。

- 実際に存在するサーフェスとcanonical route
- 認証・認可条件とrole
- legacy aliasと廃止手順
- 対応viewport、offline範囲、ブラウザ要件
- 製品固有の用語、状態、データ機密区分
- route catalog、access-control test、accessibility testなどの実行可能な検査

自然言語の共有規約だけで検証可能な契約を代替せず、製品側のテストとCIで強制してください。
