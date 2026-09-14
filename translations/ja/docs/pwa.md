# PWAとして利用する

> **参考訳（非正本）:** この文書は `docs/pwa.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

このガイドは `mkdocs.yml` と `docs/manifest.webmanifest` で構成される、`agent-policy` という **Policy プロバイダーのローカルドキュメントビルド**を説明します。コンシューマーとプロバイダー保守者の双方に向けた閲覧操作の案内です。PWA のインストールは文書を開くためのもので、Skill や CLI のインストール、リポジトリへの Policy 導入、オフラインのツールチェーン実行環境の提供は行いません。これらは [はじめに](getting-started.md) と [管理対象リポジトリの運用](managed-operation.md) を参照してください。

統合リポジトリドキュメント [templates.moukaeritai.work](https://templates.moukaeritai.work/) は Site が所有する PWA を実行します。製品の識別、Service Worker、キャッシュ範囲、更新と鮮度の挙動は Site 正本の [PWA 契約](https://github.com/TakashiSasaki/templates/blob/site/PWA.md) が定義します。このページが Site に公開されても、以下のローカル動作を統合ランタイムの契約として解釈してはいけません。

Policy の [ドキュメントワークフロー](documentation-publication.md) はビルドのみを行い、ローカルビルドをデプロイしません。以下は、このビルドを独立したサイトとして配信し、インストールと Service Worker に対応するブラウザ環境で利用する場合の案内です。ルートスコープのローカル資産は、統合 Site 内に別の PWA を埋め込むための手順ではありません。

## プロバイダーローカルの閲覧操作

プロバイダーローカルのドキュメントサイトは、対応ブラウザからProgressive Web App（PWA）としてインストールできます。インストール後は、OSのアプリ一覧、ホーム画面、スタートメニューなどから独立したウィンドウで起動できます。

### インストール

#### Android／Chrome系ブラウザ

ブラウザのメニューから「アプリをインストール」または「ホーム画面に追加」を選択します。インストール可能と判定された場合は、アドレスバーにもインストール操作が表示されます。

#### デスクトップ版Chrome／Edge

アドレスバーのインストールアイコン、またはブラウザメニューの「agent-policyをインストール」を使用します。

#### iPhone／iPad

Safariの共有メニューから「ホーム画面に追加」を選択します。ブラウザによって、利用できるPWA機能には差があります。

### 画面の向き

モバイル端末でインストール済みPWAとして起動した場合は、ポートレイト（縦長）の主方向を要求します。Web App Manifestの`orientation`を`portrait-primary`に設定し、standalone表示ではScreen Orientation APIによる固定も試行します。

通常のブラウザタブ、API非対応ブラウザ、OS側で向き固定が拒否された環境では、端末側の画面回転設定が優先されます。

### オフライン動作

Service Workerは、アプリの基本資産と以前表示した同一オリジンのページをキャッシュします。ネットワークへ接続できない場合は、キャッシュ済みページまたはオフライン案内を表示します。

ドキュメントは更新されるため、オンライン時にはネットワーク上の最新版を優先します。

### 更新

新しいService Workerが配信されると、自動的に有効化されます。表示内容が古い場合は、ページを再読み込みするか、アプリを終了して再起動してください。

## プロバイダー保守の境界

ローカル動作を変更する場合は `docs/manifest.webmanifest`、`docs/assets/javascripts/pwa.js`、`docs/service-worker.js` を確認し、[ローカルドキュメントビルド](documentation-publication.md#local-build-reproduction) を検証します。デプロイと統合 PWA は Site の責務です。このガイドの公開は、Site のランタイム資産を選択したり、インストール動作を変更したりするものではありません。
