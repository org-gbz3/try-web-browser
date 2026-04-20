# Repository Security Checklist

このテンプレートから作成した各リポジトリで、作成直後に確認しておくべきセキュリティチェックです。

## チェック記録

| 項目 | 記録 |
|------|------|
| チェック実施日 | YYYY-MM-DD |
| リポジトリ名 | |
| 確認者 | |
| 備考 | |

## 初期セキュリティチェック

### テンプレートから引き継がれる設定の確認

- [ ] Dependabot 関連のデフォルト設定が有効になっている
  - `Dependency graph`
  - `Dependabot alerts`
  - `Dependabot security updates`
- [ ] Branch protection rules が引き継がれている
  - `Settings -> Rules -> Rulesets` で `protect-main` が存在する

### リポジトリ作成後に個別設定する項目

- [ ] `Require status checks to pass` を有効にした
  - `Settings -> Rules -> Rulesets` の対象 ruleset で有効化する
- [ ] Actions の SHA ピンニングを有効にした
  - `Settings -> Actions -> General -> Actions permissions` で `Require actions to be pinned to a full-length commit SHA` を ON にする
- [ ] Dependabot for Actions を設定した
  - `.github/dependabot.yml` に `github-actions` の更新設定が存在する
- [ ] Code scanning が有効になっていることを確認した（Public リポジトリの場合）
  - `Security -> Code scanning` で Code scanning が有効であることを確認する
  - `.github/workflows/codeql-analysis.yml` が存在することを確認する
- [ ] `.gitignore` をプロジェクト特性に合わせてカスタマイズした
  - 使用する言語・ツールの生成物、ローカル設定、秘密情報が適切に除外されることを確認する
- [ ] ワークフローの `GITHUB_TOKEN` 権限を最小化した
  - `Settings -> Actions -> General -> Workflow permissions` で `Read repository contents and packages permissions` を選択する
  - 各ワークフローでも `permissions: contents: read` など必要最小限を明示する
- [ ] Environment protection rules を設定した
  - デプロイ対象がある場合に `Settings -> Environments` で `Required reviewers` などを設定する

## 補足

- この README には、リポジトリ単位で毎回確認する項目のみを記載しています。
- アカウント単位のデフォルト設定や、テンプレートリポジトリ作成時に一度だけ行う設定は対象外です。
- `Code scanning` は Public リポジトリの場合の確認項目です。
- `Environment protection rules` は利用する Environment がある場合のみ確認対象です。
