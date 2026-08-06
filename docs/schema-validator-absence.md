# Schema and validator absence on the `skill` branch

調査日: 2026-08-06

## 現状

skill ブランチには、`schemas/` ディレクトリも、データスキーマを検証する validator も存在しない。しかしこれは削除忘れではなく、ブランチ初出自体がスキーマ/validator を持たない設計になっている。

## 根拠

- skill ブランチ（PR #81）は、元から `schemas/` ディレクトリやバリデータコードを追加しておらず、削除履歴も存在しない。
- データスキーマ群とその検証スクリプトは、`webapp` ブランチ（8 ファイル）と `policy` ブランチ（3 ファイル）にのみ存在し、現時点でも残存している。
- `site` ブランチにも `schemas/` はなく、PR #71 の Pages ルート削除以降、データ系は skill にも site にも引き継がれていない。
- リネーム移行時も、webapp/policy から skill へのデータ系引き継ぎは実施されていない。

## 理由と判断

skill ブランチは、あくまで「ドキュメント公開カタログ」の canonical source を管理するブランチであり、実行コードやデータスキーマは本来の責務外である。スキーマや validator は `webapp`/`policy` の implementation 契約であり、契約のソースオブザーバーも同ブランチ側にある。そのため、意図的に skill 側へ含めていない。

## 注意点

- 今後、skill ブランチでスキーマの truth を宣言する設計に変更する場合は、`webapp`/`policy` のスキーマを共有リポジトリ経由で参照するか、スキーマと validator を skill へ新規追加する設計検討が必要になる。
- 現状の `docs/publication-maintenance.md` のスキーマはカタログ構造のみを対象としているので、データスキーマを扱う場合は docs 配下のスキーマ、または別の参照パスを別途定義すること。
