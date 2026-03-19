<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Aim. Iterate. Arrive.</b></h2>

<p align="center">
  <i>Codex のための自律型目標駆動実験エンジン。</i>
</p>

<p align="center">
  <a href="https://developers.openai.com/codex/skills"><img src="https://img.shields.io/badge/Codex-Skill-blue?logo=openai&logoColor=white" alt="Codex Skill"></a>
  <a href="https://github.com/leo-lilinxiao/codex-autoresearch"><img src="https://img.shields.io/github/stars/leo-lilinxiao/codex-autoresearch?style=social" alt="GitHub Stars"></a>
  <a href="../../LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
</p>

<p align="center">
  <a href="../../README.md">English</a> ·
  <a href="README_ZH.md">🇨🇳 中文</a> ·
  <b>🇯🇵 日本語</b> ·
  <a href="README_KO.md">🇰🇷 한국어</a> ·
  <a href="README_FR.md">🇫🇷 Français</a> ·
  <a href="README_DE.md">🇩🇪 Deutsch</a> ·
  <a href="README_ES.md">🇪🇸 Español</a> ·
  <a href="README_PT.md">🇧🇷 Português</a> ·
  <a href="README_RU.md">🇷🇺 Русский</a>
</p>

<p align="center">
  <a href="#クイックスタート">クイックスタート</a> ·
  <a href="#何をするのか">何をするのか</a> ·
  <a href="#アーキテクチャ">アーキテクチャ</a> ·
  <a href="#モード">モード</a> ·
  <a href="#設定">設定</a> ·
  <a href="#クロスラン学習">学習</a> ·
  <a href="#並列実験">並列</a> ·
  <a href="../GUIDE.md">操作マニュアル</a> ·
  <a href="../EXAMPLES.md">レシピ集</a>
</p>

---

## クイックスタート

**1. インストール：**

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

または Codex 内で skill installer を使用：
```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

**2. プロジェクトで Codex を開き、やりたいことを伝える：**

```text
$codex-autoresearch
TypeScript コードの any 型を全て除去してほしい
```

**3. Codex がスキャンし、確認した後、自律的に反復する：**

```
Codex: src/**/*.ts に 47 個の `any` が見つかりました。

       確認済み：
       - 目標：src/**/*.ts の全ての any 型を除去
       - 指標：any の出現回数（現在 47）、方向：減少
       - 検証：grep カウント + tsc --noEmit ガード

       要確認：
       - 全て除去するまで実行、または N 回の反復で上限を設定？

       "go" と返信して開始、または変更点を教えてください。

あなた: go、一晩中走らせて。

Codex: 開始 -- ベースライン：47。中断されるまで反復を継続します。
```

改善は蓄積され、失敗はロールバックされ、全てが記録されます。

その他のインストール方法は [INSTALL.md](../INSTALL.md) を参照。完全な操作マニュアルは [GUIDE.md](../GUIDE.md) を参照。

---

## 何をするのか

コードベース上で「修正-検証-判断」ループを実行する Codex skill です。各反復で1つのアトミックな変更を行い、機械的な指標で検証し、結果を保持または破棄します。進捗は git に蓄積され、失敗は自動的にリバートされます。あらゆる言語、あらゆるフレームワーク、あらゆる測定可能な目標に対応します。

[Karpathy の autoresearch](https://github.com/karpathy/autoresearch) の理念に触発され、ML の枠を超えて汎用化しました。

### なぜこれを作ったのか

Karpathy の autoresearch は、シンプルなループ -- 修正、検証、保持または破棄、繰り返し -- が一晩で ML の訓練をベースラインから新たな高みに押し上げられることを実証しました。codex-autoresearch はそのループをソフトウェアエンジニアリングにおける数値を持つ全てのものに汎用化します。テストカバレッジ、型エラー、パフォーマンスレイテンシ、lint 警告 -- 指標があれば、自律的に反復できます。

---

## アーキテクチャ

```
              +---------------------+
              |  Environment Probe  |  <-- Phase 0: detect CPU/GPU/RAM/toolchains
              +---------+-----------+
                        |
              +---------v-----------+
              |  Session Resume?    |  <-- check for prior run artifacts
              +---------+-----------+
                        |
              +---------v-----------+
              |   Read Context      |  <-- read scope + lessons file
              +---------+-----------+
                        |
              +---------v-----------+
              | Establish Baseline  |  <-- iteration #0
              +---------+-----------+
                        |
         +--------------v--------------+
         |                             |
         |  +----------------------+   |
         |  | Choose Hypothesis    |   |  <-- consult lessons + perspectives
         |  | (or N for parallel)  |   |      filter by environment
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | Make ONE Change      |   |
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | git commit           |   |
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | Run Verify + Guard   |   |
         |  +---------+------------+   |
         |            |                |
         |        improved?            |
         |       /         \           |
         |     yes          no         |
         |     /              \        |
         |  +-v------+   +----v-----+ |
         |  |  KEEP  |   | REVERT   | |
         |  |+lesson |   +----+-----+ |
         |  +--+-----+        |       |
         |      \            /         |
         |   +--v----------v---+      |
         |   |   Log Result    |      |
         |   +--------+--------+      |
         |            |               |
         |   +--------v--------+      |
         |   |  Health Check   |      |  <-- disk, git, verify health
         |   +--------+--------+      |
         |            |               |
         |     3+ discards?           |
         |    /             \         |
         |  no              yes       |
         |  |          +----v-----+   |
         |  |          | REFINE / |   |  <-- pivot-protocol escalation
         |  |          | PIVOT    |   |
         |  |          +----+-----+   |
         |  |               |         |
         +--+------+--------+         |
         |         (repeat)           |
         +----------------------------+
```

ループは中断されるまで（無制限）または正確に N 回の反復（`Iterations: N` で上限を設定）まで実行されます。

**擬似コード：**

```
PHASE 0: 環境をプローブし、セッション再開の可否を確認
PHASE 1: コンテキスト + 教訓ファイルを読み込む

LOOP (永久 or N 回):
  1. 現在の状態 + git 履歴 + 結果ログ + 教訓を確認
  2. 仮説を1つ選択（パースペクティブを適用し、環境でフィルタリング）
     -- 並列モードがアクティブな場合は N 個の仮説を選択
  3. アトミックな変更を1つ実施
  4. git commit（検証の前に）
  5. 機械的検証 + guard を実行
  6. 改善 -> 保持（教訓を抽出）。悪化 -> git reset。クラッシュ -> 修正またはスキップ。
  7. 結果を記録
  8. ヘルスチェック（ディスク、git、検証の健全性）
  9. 3回以上連続破棄 -> REFINE、5回以上 -> PIVOT、2回の PIVOT -> Web 検索
  10. 繰り返す。決して止めない。決して質問しない。
```

---

## モード

7つのモード、統一された呼び出しパターン：`$codex-autoresearch` の後に自然言語で一文。Codex が自動的にモードを検出し、対話を通じて設定を補完します。

| モード | 使用場面 | 停止条件 |
|--------|----------|----------|
| `loop` | 測定可能な最適化目標がある | 中断または N 回の反復 |
| `plan` | 目標はあるが設定が不明 | 設定ブロックが生成される |
| `debug` | 証拠に基づく原因分析が必要 | 全仮説をテスト済みまたは N 回の反復 |
| `fix` | 壊れたものを修復する必要がある | エラー数がゼロになる |
| `security` | 構造化された脆弱性監査が必要 | 全攻撃面をカバーまたは N 回の反復 |
| `ship` | ゲート付きリリース検証が必要 | 全チェック項目が通過 |
| `exec` | CI/CD パイプライン、対話不要 | N 回の反復（常に上限あり）、JSON 出力 |

**クイック選択：**

```
"X を改善したい"                -->  loop（指標が不明なら plan）
"何かが壊れている"              -->  fix（原因が不明なら debug）
"このコードは安全か？"          -->  security
"リリースの準備をする"          -->  ship
codex exec --skill ...          -->  exec（CI/CD、ウィザードなし）
```

---

## 設定

### 必須フィールド（loop モード）

| フィールド | 型 | 例 |
|------------|------|------|
| `Goal` | 達成目標 | `Reduce type errors to zero` |
| `Scope` | 変更可能なファイル glob | `src/**/*.ts` |
| `Metric` | 追跡する数値 | `type error count` |
| `Direction` | `higher` または `lower` | `lower` |
| `Verify` | 指標を出力するコマンド | `tsc --noEmit 2>&1 \| wc -l` |

### オプションフィールド

| フィールド | デフォルト | 用途 |
|------------|------------|------|
| `Guard` | なし | リグレッション防止の安全コマンド |
| `Iterations` | 無制限 | N 回の反復で上限を設定 |
| `Run tag` | 自動 | 今回の実行のラベル |
| `Stop condition` | なし | カスタム早期停止ルール |

必須フィールドが不足している場合、インタラクティブウィザードがリポジトリをスキャンし、開始前に必ず確認を取ります（最大5ラウンド）。フィールド名を知る必要はありません。

### 二重ゲート検証

2つのコマンドがそれぞれ異なる役割を担います：

- **Verify** = 「目標指標は改善したか？」（進捗を測定）
- **Guard** = 「他に壊れたものはないか？」（リグレッションを防止）

```text
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'   # カバレッジは上がったか？
Guard: npx tsc --noEmit                                                              # 型は通るか？
```

Verify が通過しても Guard が失敗した場合、変更は再調整されます（最大2回）。その後ロールバックされます。Guard 対象のファイルは変更されません。

---

## クイック判断ガイド

| やりたいこと | モード | 主要設定 |
|-------------|--------|----------|
| 一晩かけて指標を一方向に押し進める | `loop` | Goal + Metric + Verify |
| どの指標を追跡すべきか把握する | `plan` | Goal のみ |
| 何かが壊れている原因を見つける | `debug` | Scope + Symptom |
| 失敗しているテスト/型/lint を通す | `fix` | Target コマンド |
| コードの脆弱性を監査する | `security` | Scope + Focus |
| 自信を持ってリリースする | `ship` | "ship it" または "dry run first" と伝える |
| CI/CD で対話なしに実行する | `exec` | 全フィールド事前指定 + Iterations |

---

## モード詳細

### loop

デフォルトモード。測定可能な目標に向けて反復します。

```
あなた: TypeScript コードの any 型を全て除去してほしい

Codex: src/**/*.ts に 47 個の `any` が見つかりました。

       確認済み：
       - 目標：全ての any 型を除去
       - 指標：any の回数（現在 47）、方向：減少
       - 検証：grep カウント、ガード：tsc --noEmit

       要確認：
       - ゼロになるまで実行、または N 回の反復で上限を設定？

       "go" と返信して開始。

あなた: go、一晩中走らせて。
```

### plan

曖昧な目標を検証済みのループ設定に変換します。

```
あなた: API を速くしたいが、どこから始めればいいかわからない

Codex: リポジトリをスキャンしました。API 層は src/api/ にあり、Express + Prisma を使用しています。

       要確認：
       - 重視するのは p95 レイテンシ、スループット、コールドスタートのどれですか？
       - API 全体をベンチマークしますか、それとも特定のエンドポイントですか？

       優先順位を教えてください。

あなた: p95 レイテンシ、/search エンドポイントが最も遅い。
```

### debug

証拠駆動のバグ追跡。各反復で1つの反証可能な仮説をテストします。

```
あなた: API が高負荷時にランダムに 503 を返す。原因がわからない

Codex: src/db/pool.ts にコネクションプーリング、src/middleware/ にレート制限、
       そしてエラーバウンダリのない 3 つの非同期ハンドラがあります。

       確認済み：
       - 症状：並行負荷下で断続的に 503 が発生
       - 範囲：src/api/、src/db/、src/middleware/

       要確認：
       - いつから発生していますか？特定の変更後ですか、それとも以前からですか？
       - 原因が見つかったら修正もしますか？

       コンテキストを教えてください。

あなた: 先週のコネクションプールリファクタリング後に始まった。まず原因を特定して。
```

### fix

エラー数がゼロになるまで反復的に修復します。

```
あなた: リファクタリング後に pytest が 12 個のテストで失敗している

Codex: tests/ に 12 個の失敗があります。

       確認済み：
       - 目標：全ての pytest テストを通す
       - 現在：12 個の失敗

       要確認：
       - ruff でガードして lint の問題を防ぎますか？
       - 全て修正しますか、それとも特定のモジュールに集中しますか？

       "go" と返信して開始。

あなた: 全て修正、ruff でガード。Go。
```

### security

読み取り専用の STRIDE + OWASP + レッドチーム監査。全ての発見にコード証拠が必要です。

```
あなた: API にインジェクション脆弱性がないか確認して

Codex: 確認済み：
       - 範囲：src/api/ と src/middleware/（14 ファイル）
       - 重点：SQL インジェクション、XSS、入力バリデーション

       要確認：
       - レポートのみ、または重大な問題も修正しますか？
       - 認証/アクセス制御もカバーしますか？

       ご希望を教えてください。

あなた: まずレポート、認証も確認して。
```

### ship

ゲート付きリリース検証。何をリリースするか（PR、デプロイ、リリース）を自動検出します。

```
あなた: リリースして

Codex: 検出：main への PR、3 コミット。

       確認済み：
       - 種別：コード PR
       - 対象：main ブランチ

       要確認：
       - まずドライランしますか、それとも本番に進みますか？
       - リリース後の監視は？（5 分 / 15 分 / スキップ）

       ご希望を教えてください。

あなた: まずドライラン。
```

各モードの詳細な使用方法と高度なオプションは [GUIDE.md](../GUIDE.md) を参照。

---

## モードの組み合わせ

モードは順序的に組み合わせることができます：

```
plan  -->  loop              # まず設定を生成し、次に実行
debug -->  fix               # まずバグを見つけ、次に修復
security + fix               # 監査と修復を一度に実施
```

---

## クロスラン学習

全ての実行から構造化された教訓が抽出されます -- 何が有効だったか、何が失敗したか、そしてなぜか。教訓は `autoresearch-lessons.md`（結果ログと同様にコミットされない）に保存され、将来の実行開始時に参照されることで、実績のある戦略に仮説生成を偏らせ、既知の行き止まりを回避します。

- 保持された各反復後にポジティブな教訓を記録
- 各 PIVOT 判断後に戦略的教訓を記録
- 実行完了時にサマリー教訓を記録
- 容量：最大 50 エントリ、古いエントリは時間減衰で要約

詳細は `references/lessons-protocol.md` を参照。

---

## スマートスタック回復

失敗後に盲目的にリトライするのではなく、ループは段階的なエスカレーションシステムを使用します：

| トリガー | アクション |
|----------|-----------|
| 3 回連続の破棄 | **REFINE** -- 現在の戦略内で調整 |
| 5 回連続の破棄 | **PIVOT** -- 戦略を放棄し、根本的に異なるアプローチを試行 |
| 改善なしの PIVOT 2 回 | **Web 検索** -- 外部の解決策を探索 |
| 改善なしの PIVOT 3 回 | **ソフトブロッカー** -- 警告を発し、より大胆な変更で継続 |

1 回の成功した保持で全てのカウンターがリセットされます。詳細は `references/pivot-protocol.md` を参照。

---

## 並列実験

分離された git worktree 内のサブエージェントワーカーを使用して、複数の仮説を同時にテストします：

```
オーケストレーター（メインエージェント）
  +-- ワーカー A (worktree-a) -> 仮説 1
  +-- ワーカー B (worktree-b) -> 仮説 2
  +-- ワーカー C (worktree-c) -> 仮説 3
```

オーケストレーターが最良の結果を選択し、マージし、残りを破棄します。ウィザード中に「並列実験を有効にしますか」に「はい」と答えることで有効化できます。worktree がサポートされていない場合はシリアル実行にフォールバックします。

詳細は `references/parallel-experiments-protocol.md` を参照。

---

## セッション再開

Codex が以前の中断された実行（結果ログ、教訓ファイル、実験コミット）を検出した場合、最初からやり直すのではなく、最後の整合状態から再開できます：

- **整合状態：** 即座に再開、ウィザードをスキップ
- **部分的に整合：** ミニウィザード（1 ラウンド）で再確認
- **不整合または異なる目標：** フレッシュスタート（古いログはリネーム）

詳細は `references/session-resume-protocol.md` を参照。

---

## CI/CD モード（exec）

自動化パイプライン向けの非対話モード。全ての設定は事前に指定されます -- ウィザードなし、常に上限あり、JSON 出力。

```yaml
# GitHub Actions の例
- name: Autoresearch optimization
  run: codex exec --skill codex-autoresearch
         --goal "Reduce type errors" --scope "src/**/*.ts"
         --metric "type error count" --direction lower
         --verify "tsc --noEmit 2>&1 | grep -c error"
         --iterations 20
```

終了コード：0 = 改善、1 = 改善なし、2 = ハードブロッカー。

詳細は `references/exec-workflow.md` を参照。

---

## 結果ログ

各反復は TSV ファイル（`research-results.tsv`）に記録されます：

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

5 回の反復ごとに進捗サマリーが出力されます。有限回の実行終了時にはベースラインから最良値までのサマリーが出力されます。

---

## セキュリティモデル

| 懸念事項 | 対処方法 |
|----------|----------|
| ダーティなワークツリー | ループは開始を拒否。`plan` モードまたはクリーンなブランチを提案 |
| 失敗した変更 | `git reset --hard HEAD~1` で履歴をクリーンに保つ。結果ログが監査証跡 |
| Guard の失敗 | 最大2回の再調整後にロールバック |
| 構文エラー | 即座に修正。反復としてカウントしない |
| ランタイムクラッシュ | 最大3回の修正試行後にスキップ |
| リソース枯渇 | リバートし、より小さな変更を試行 |
| プロセスのハング | タイムアウト後に終了、リバート |
| スタック（3回以上連続破棄） | REFINE で戦略を調整、5回以上は PIVOT で新アプローチへ、必要に応じて Web 検索にエスカレート |
| ループ中の不確実性 | ベストプラクティスを自律的に適用。ユーザーへの質問は決して行わない |
| 外部への副作用 | `ship` モードはプレローンチウィザードで明示的な確認を要求 |
| 環境の制約 | 起動時にプローブし、実行不可能な仮説を自動的にフィルタリング |
| 中断されたセッション | 次回の呼び出し時に最後の整合状態から再開 |

---

## プロジェクト構造

```
codex-autoresearch/
  SKILL.md                          # skill エントリポイント（Codex が読み込む）
  README.md                         # 英語ドキュメント
  CONTRIBUTING.md                   # コントリビューションガイド
  LICENSE                           # MIT
  agents/
    openai.yaml                     # Codex UI メタデータ
  image/
    banner.png                      # プロジェクトバナー
  docs/
    INSTALL.md                      # インストールガイド
    GUIDE.md                        # 操作マニュアル
    EXAMPLES.md                     # 分野別レシピ集
    i18n/
      README_ZH.md                  # 中国語
      README_JA.md                  # 本ファイル
      README_KO.md                  # 韓国語
      README_FR.md                  # フランス語
      README_DE.md                  # ドイツ語
      README_ES.md                  # スペイン語
      README_PT.md                  # ポルトガル語
      README_RU.md                  # ロシア語
  scripts/
    validate_skill_structure.sh     # 構造検証スクリプト
  references/
    core-principles.md              # 汎用原則
    autonomous-loop-protocol.md     # ループプロトコル仕様
    plan-workflow.md                # plan モード仕様
    debug-workflow.md               # debug モード仕様
    fix-workflow.md                 # fix モード仕様
    security-workflow.md            # security モード仕様
    ship-workflow.md                # ship モード仕様
    exec-workflow.md                # CI/CD 非対話モード仕様
    interaction-wizard.md           # インタラクティブセットアップ契約
    structured-output-spec.md       # 出力フォーマット仕様
    modes.md                        # モードインデックス
    results-logging.md              # TSV フォーマット仕様
    lessons-protocol.md             # クロスラン学習
    pivot-protocol.md               # スマートスタック回復（PIVOT/REFINE）
    web-search-protocol.md          # スタック時の Web 検索
    environment-awareness.md        # ハードウェア/リソース検出
    parallel-experiments-protocol.md # サブエージェント並列テスト
    session-resume-protocol.md      # 中断された実行の再開
    health-check-protocol.md        # セルフモニタリング
    hypothesis-perspectives.md      # マルチレンズ仮説推論
```

---

## FAQ

**指標はどう選ぶ？** `Mode: plan` を使用してください。コードベースを分析し、提案してくれます。

**どの言語に対応？** 全てです。プロトコルは言語に依存しません。検証コマンドのみがドメイン固有です。

**どうやって止める？** Codex を中断するか、`Iterations: N` を設定してください。コミットは検証の前に行われるため、git の状態は常に一貫しています。

**security モードはコードを変更する？** いいえ。読み取り専用の分析です。セットアップ時に Codex に「重大な問題も修正して」と伝えることで、修復を選択できます。

**何回反復する？** タスクによります。的を絞った修正は 5 回、探索的なものは 10-20 回、一晩の実行は無制限です。

**実行間で学習する？** はい。各実行後に教訓が抽出され、次回の実行開始時に参照されます。教訓ファイルはセッション間で保持されます。

**中断後に再開できる？** はい。次回の呼び出し時に、以前の実行を検出し、最後の整合状態から再開します。

**Web 検索は可能？** はい。複数回の戦略ピボット後にスタックした場合に使用されます。Web 検索結果は仮説として扱われ、機械的に検証されます。

**CI で使うには？** `Mode: exec` または `codex exec` を使用してください。全ての設定は事前に指定され、出力は JSON 形式で、終了コードが成功/失敗を示します。

**複数のアイデアを同時にテストできる？** はい。セットアップ中に並列実験を有効にしてください。git worktree を使用して最大 3 つの仮説を同時にテストします。

---

## 謝辞

本プロジェクトは [Karpathy の autoresearch](https://github.com/karpathy/autoresearch) の理念を基に構築されています。Codex skills プラットフォームは [OpenAI](https://openai.com) によって提供されています。

---

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

---

## ライセンス

MIT -- [LICENSE](../../LICENSE) を参照。
