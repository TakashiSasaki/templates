---
description: Google AI Studio Build modeでrepositoryを編集、検証、GitHubへexportする際の標準運用を説明します。
---

# Google AI Studio Build mode operation

このページは、Google AI Studio Build modeで既存repositoryを編集し、workspace内で検証した後にGitHubへexportする作業の標準運用を定義します。

Google AI Studio固有の実行環境を対象とする非規範的なガイドです。製品repository固有のbranch、database、deployment、security、verification commandは、各repositoryのinstructionsとproject policyで定義します。

## 責任境界

Google AI Studioは、GitHubからprojectをimportし、複数fileを編集し、live previewを表示し、GitHub repositoryへ変更をexportできます。ただし、作業中に観測できるworkspace stateと、export後のGitHub repository stateは別のevidence layerです。

標準的な責任分担は次です。

| 担当 | 責任 |
|---|---|
| Google AI Studio | workspaceの確認と編集、repository-local command、live preview、repository-local verification、GitHub exportの要求 |
| 外部repository observer | exported revisionの特定、前回baselineとの差分、remote CI、permission・dependency・metadata変更、最終acceptance |

AI Studioから直接確認できないcommit SHA、remote branch state、GitHub Actions結果、external audit結果を推測してはいけません。観測できない項目は`NOT_OBSERVABLE`、実行していない項目は`NOT_RUN`、確認が完了していない項目は`UNVERIFIED`と報告します。

## 作業開始時のbaseline sentinel

Git revisionを直接確認できない場合は、次のtaskが依存するworkspace capabilityをbaseline sentinelとして確認します。

- 必要なfileが存在する
- 必要なsymbol、route、command、configurationが存在する
- 前工程で成立した主要なuser-visible behaviorが存在する
- repositoryが定めるcentral verification commandが存在する

Baseline sentinelはcommit identityの代替ではありません。表示文言、file ordering、軽微なstyle差など、次のtaskが依存しない事項を過剰なsentinelにして作業を停止させません。

重大なbaseline mismatchは報告してdependent workを止めます。独立して安全に進められる作業は、軽微なmismatchだけを理由に停止しません。

## Task promptの構成

AI Studioへ渡すtask promptは、repository内の`AGENTS.md`、project policy、該当skillを前提とする差分指示として構成します。恒久規約や過去作業の詳細を毎回再掲しません。

標準構成は次です。

```text
Goal
Baseline sentinel
Primary outcomes
Hard boundaries
Implementation scope
Verification
Export condition
Final report
```

制約は次の三種類に分類します。

| 分類 | 意味 |
|---|---|
| Hard boundary | 違反が必要なら作業を停止する安全、data、authorization上の境界 |
| Preserved invariant | 変更後も維持する既存behavior、compatibility、data meaning |
| Planning boundary | 想定する変更範囲。逸脱は説明するが、material impactがなければそれだけで自動FAILにしない |

Promptにはtask固有の到達点、境界、対象、verificationだけを残します。背景説明、過去のstride、詳細な外部監査手順、既にrepository instructionsへ存在する一般規則は省略します。

## 実装単位

大きな復元またはintegration作業は、利用可能なthin vertical sliceへ分割します。各作業単位は、小さくても入力からuser-visible resultまで到達できる形を優先します。

外部serviceへまだ接続できない場合は、次のような境界を先に完成させます。

- runtime-neutral model
- providerまたはadapter interface
- 明示的なunconfigured state
- development-only fixtureまたはstub
- loading、success、negative result、errorの区別
- cancellationとstale-result protection

`unconfigured`は、serviceへ問い合わせてnegative resultを得た状態とは区別します。問い合わせていない状態を`not found`などのdomain resultとして表示してはいけません。

## Verification

Verification evidenceは次のlayerへ分離します。

| Layer | 例 |
|---|---|
| Repository-local | typecheck、build、unit test、schema validator、repository central verification |
| Preview-dependent | browser navigation、reload、UI interaction、AI Studio preview behavior |
| Hardware-dependent | camera、microphone、NFC、Bluetooth、USB、serial |
| Remote | GitHub Actions、deployment、external service |
| Independent audit | exported revisionのdiff、regression、hard boundaryの外部確認 |

一つのlayerのPASSを別layerのPASSとして報告しません。例えば、build PASSはbrowser reload、hardware API、remote CIのPASSを意味しません。

Central verificationがFAILした場合は原因を修正して再実行できます。corrective回数を機械的な完了条件にせず、working outcome、安全境界、検証結果を優先します。

## GitHub export

Repository-local verificationがPASSし、primary outcomeが成立し、hard boundary violationがない場合にGitHub exportを要求します。

Export前に次を確認します。

- temporary download、archive、extraction tree、patch scriptが残っていない
- dependency、permission、platform capabilityの追加が意図されたものか
- secretsまたはcredentialsがsourceへ書かれていない
- generated fileを直接編集していない
- repositoryが指定するexport destinationと現在の連携先を確認した

任意branchへexportできると仮定してはいけません。branch controlが必要でAI StudioのUIで選択できない場合は、ZIP exportまたは完全なGit環境へのhandoffを使用します。

## Export後の外部監査

外部監査では、前回accepted revisionとexport後revisionの差分に集中します。

1. Exported revisionを特定する。
2. 前回accepted revisionとの差分とchanged filesを取得する。
3. 変更を`intended`、`derived`、`incidental but harmless`、`unexplained and material`へ分類する。
4. Primary outcomeとpreserved invariantsを確認する。
5. Hard boundary、dependency、permission、metadata、temporary artifactを確認する。
6. Remote CIが現在のrevisionを対象としているか確認する。
7. Acceptance、follow-up、または明示的なrebaselineを決定する。

想定外のdocumentation fileやmetadata変更があることだけでは自動的にFAILにしません。runtime、security、data boundary、dependency、将来のagent behaviorへの影響を評価します。

## `metadata.json`とplatform-generated changes

Google AI Studioのweb appでは、`metadata.json`の`requestFramePermissions`にcamera、microphone、geolocation、Bluetoothなどのpermission requestを記録できます。Export後は少なくとも次を確認します。

- `requestFramePermissions`
- capability declaration
- secretまたはserver-side featureに関するmetadata
- dependencyとscript
- root-level temporary file

Permissionまたはcapabilityの追加は必要性を確認します。追加されたという事実だけでも、AI Studioが生成したという事実だけでも、正当化にはなりません。

## External artifact

Historical source、archive、reference bundleなどをAI Studioへ渡す場合は、`external-artifact-intake` profileの規約を適用します。

- mutable branch URLよりimmutable revisionを含むURLを優先する
- 修正版artifactでは同じpathを置換せず、新しいartifact nameまたはrevisionを使う
- digest、archive integrity、repository-authoritative validatorを分けて実行する
- artifact依存作業とartifact非依存作業を分離する
- reference-only materialを暗黙にinstallまたはactivateしない

## 完了報告

完了報告は短く、外部監査へ必要な事実だけを含めます。

```text
Outcome
Files changed
Repository-local verification
Preview or hardware verification
Hard boundaries
GitHub export action
Unobservable evidence
Remaining work
```

標準状態語は次です。

```text
PASS
FAIL
PARTIAL
SKIP
NOT_RUN
NOT_OBSERVABLE
UNVERIFIED
```

Implemented、executed、verified、inferredを区別し、観測できないremote stateを成功として報告しません。

## 参照

- [Build apps in Google AI Studio](https://ai.google.dev/gemini-api/docs/aistudio-build-mode)
- [Develop Full-Stack Apps in Google AI Studio](https://ai.google.dev/gemini-api/docs/aistudio-fullstack)
