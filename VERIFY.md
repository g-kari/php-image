# パッチ適用の確認方法

このリポジトリは通常の古い PHP バイナリをそのまま再配布するものではありません。
次の **公式 CVE 専用ブランチの完全な固定ソースツリー** から PHP 本体、FPM、同梱共有拡張を再構築します。

- PHP 7.4: `712e60f9edfd03f0960fc4fc3c2c375f42b90aa2`
- PHP 8.0: `82f8f31b16a035c1b67cc253e79f7cc288f4cc20`
- PHP 8.1: `1d7dec178a094e6e75b229ce22754045f8c6070a`

[固定ソースと公式コミットへのリンク](sources.lock.json)

公式コミットの表現は “Minimal mitigation for EOL version” です。
CVE-2026-109618 と CVE-2026-109619 に対する限定的な緩和策であり、PHP/OS の保守再開や全脆弱性修正を意味しません。
ソース変更によりセッションの upload-progress callback は無効となり、メモリ枯渇時は従来の shutdown callback が動かずプロセス終了する経路があります。

## 配布物に同梱する証跡

- `source.json`: 完全な公式ソース SHA、tree SHA、実ビルド用 tar の SHA256。通常リリースの 8.2 は Git archive ではなく署名済み配布 tar なので tree は null で、元 tar.xz と .asc も保存します。
- `provenance.json`: このリポジトリのレシピ SHA、系列、CPU、CI URL、通過した試験と未検証範囲。
- `binaries.sha256`: 実行した CLI/FPM の実バイト列の SHA256。
- `sbom.spdx.json`: 実ビルド/実行環境の依存パッケージ一覧。
- `fpm-test.json`: 同一 worker でのセッション連続要求、通常ファイルアップロード、意図した OOM 後の worker 補充の結果。
- `SHA256SUMS`: 配布ファイルのチェックサム。公開前に GitHub の asset size/digest と照合します。
- FPM の `IMAGE.txt`: レジストリのタグと immutable digest。認証済み push と匿名 pull 成功は別に確認します。

## Docker 内で確認

```sh
docker run --rm --network none IMAGE php -r 'echo file_get_contents("/usr/local/share/php-mitigation/source.json");'
docker run --rm --network none IMAGE sh -c 'cd / && sha256sum -c /usr/local/share/php-mitigation/binaries.sha256'
```

出力の完全な source SHA を上の公式コミットと比較してください。レシピ SHA は OCI label の
`org.opencontainers.image.revision` と provenance.json で照合できます。
PHP_VERSION という文字列が一致しただけでは対策入りとは判定しません。

## AL2 RPM 内で確認

RPM は AWS の PHP を上書きせず、独立した package/prefix/config/service に導入します。
対象 Release の build ID を確認し、明示的な絶対パスで `share/mitigation/source.json` を読んでください。
`rpm -V php74-mitigation` / `php80-mitigation` / `php81-mitigation` は導入後のファイル改変確認です。
実行バイナリの hash は Release の binaries.sha256 と比較できます。

初期 RPM は署名鍵を新規作成せず unsigned で配布します。組織の署名要件を回避したり gpgcheck を無効にしたりせず、
必要なら同梱 SRPM を既存の承認済み署名・ビルド手順で再構築してください。

これらは限定した回帰確認です。実アプリ、外部 DB/TLS、全拡張、全 upstream テストや実ホスト systemd/socket の動作を保証しません。

## 追加の AL2 PHP 8.2

8.2 は上記 EOL 最小緩和ツリーとは別で、通常の公式セキュリティリリース PHP 8.2.35 です。source.json の kind=official-release、distribution_sha256、verified_signer と固定リリースの情報を照合してください。公式 tar.xz の SHA256 は 5737b98601fe5ab1b8c5db0c82ed3158acb9283ed3081ffe2faffb9ac81455e6 です。8.2 専用テストは通常のメモリ制限超過で exit255 と shutdown callback を期待し、旧系列の exit1/コールバック無実行と混同しません。
