# Codex Autoresearch

[English](../../README.md) | **日本語**

Codex のための、自律的で測定可能な実験ループです。

数値目標を伝えると、Codex はリポジトリを調査して実行条件を確認し、1 つ変更、検証、改善の保持、失敗の取り消しを目標達成まで繰り返します。

テスト失敗数、カバレッジ、型エラー、警告、レイテンシ、バイナリサイズ、再現可能なセキュリティ検出などに使えます。

## クイックスタート

Codex でインストールします。

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

クリーンな Git リポジトリを Full Access で開くことを推奨します。

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

次に実行します。

```text
$codex-autoresearch `python3 scripts/score.py` の error_count を 0 にする
```

最初の書き込み前に、目標、変更範囲、ベースライン、ターゲット、測定コマンド、任意の guard、foreground/background を確認します。

すでに伝えた選択や承認は引き継がれます。開始後は各実験の確認を求めずに継続します。停止したバックグラウンド実行は「再開」で元の設定を続行でき、新しい方針も任意で追加できます。

## 仕組み

```text
証拠を確認 -> 1 つの仮説を変更 -> コミットして測定
                                      |
                         改善 + guard 成功: 保持
                         それ以外: git revert
                                      |
                               記録して継続
```

Codex が仮説とコード変更を担当し、制御スクリプトが Git 境界、測定、ロールバック、状態を担当します。

## Foreground と Background

| | Foreground | Background |
|---|---|---|
| 実行場所 | 現在の Codex タスク | 独立 controller |
| 継続 | 公式 Codex Goal | 1 反復につき 1 つの `codex exec` worker |
| 用途 | ライブで監視・指示 | 長時間・夜間実行 |
| 制御 | Goal の pause/resume | `$codex-autoresearch` で status/stop/resume |

Foreground は公式 Goal で継続します。Background は Goal を作らず controller が継続します。インストールによって Codex 設定は変更されません。

## 結果

未コミットの `autoresearch-results/` に保存されます。

| パス | 内容 |
|---|---|
| `run.json` | 確認済みの不変設定 |
| `events.jsonl` | 追記専用の状態・監査履歴 |
| `logs/` | 測定、guard、worker の完全な出力 |
| `runtime.json` | バックグラウンドプロセス状態 |
| `runtime.log` | controller のライフサイクル |

`events.jsonl` が唯一の実行状態です。欠損、破損、矛盾があれば推測で復旧せず、明確に失敗します。

## 履歴とレポート

```text
$codex-autoresearch show experiment history
$codex-autoresearch export experiment history as TSV
$codex-autoresearch generate an HTML report
```

履歴表と HTML は検証済みイベントから生成されます。HTML スナップショットは `autoresearch-results/report.html` に保存され、実行状態や復旧には使用されません。

## 信頼性

- 新しい実行にはクリーンな名前付き Git ブランチが必要です。
- 1 実行は 1 リポジトリ、1 指標、1 ターゲットです。
- 各実験はコミットされ、失敗は `git revert` されます。
- 範囲外変更、Git ドリフト、不正な指標、コマンド失敗、タイムアウト、ロールバック失敗はログ付きで停止します。
- 保持された指標がターゲットに達した場合だけ `complete` になります。

## 要件

- Skills と Goals を備えた現行 Codex CLI
- Python 3.11+
- Git

[インストール](../INSTALL.md)、[ユーザーガイド](../GUIDE.md)、[例](../EXAMPLES.md)も参照してください。

MIT License。着想は [Karpathy の autoresearch](https://github.com/karpathy/autoresearch) から得ています。
