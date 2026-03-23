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
  <a href="#仕組み">仕組み</a> ·
  <a href="#codexが自動で把握すること">Codexが自動で把握すること</a> ·
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
       - 実行モード：foreground と background のどちらにしますか？
       - 全て除去するまで実行、または N 回の反復で上限を設定？

       実行モードを選び、その後 "go" と返信して開始するか、
       変更点を教えてください。

あなた: Background、go。一晩中走らせて。

Codex: background 実行を開始します -- ベースライン：47。
       detached runtime がすでに反復を続けています。
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

以下の図は、まずインタラクティブな起動フローを、続いて共有されるループの中核を示します。ループに入る前に、Codex は環境を調べ、再開可能なセッションがあるか確認し、設定を確定し、`foreground` か `background` を明示的に選ばせます。

```
              +----------------------+
              |   環境プローブ       |  <-- CPU/GPU/RAM/ツールチェーンを検出
              +----------+-----------+
                         |
              +----------v-----------+
              | セッション再開?      |  <-- 以前の結果/状態を確認
              +----------+-----------+
                         |
              +----------v-----------+
              | コンテキスト読み込み |  <-- scope + 教訓 + repo 状態
              +----------+-----------+
                         |
              +----------v-----------+
              | wizard で確認        |  <-- 目標/指標/verify/guard
              | + モード選択         |      + foreground または background
              +----------+-----------+
                         |
               +---------+---------+
               |                   |
     +---------v--------+  +-------v---------+
     | foreground 実行  |  | background 実行 |
     | 現在のセッション |  | manifest + ctl  |
     | runtime files なし| | detached runtime|
     +---------+--------+  +-------+---------+
               |                   |
               +---------+---------+
                         |
              +----------v-----------+
              | 共有ループコア       |
              | baseline -> change   |
              | -> verify/guard ->   |
              | keep/discard/log     |
              +----------+-----------+
                         |
              +----------v-----------+
              | supervisor の結果    |  <-- continue / stop / needs_human
              +----------------------+
```

Foreground と background は、同じ実験プロトコルを共有します。違うのはループがどこで実行されるかだけです。foreground は現在の Codex セッション内で、background は detached runtime controller で実行されます。どちらも中断されるまで（無制限）または正確に N 回の反復（`Iterations: N` で上限を設定）まで動きます。

**擬似コード：**

```
PHASE 0: 環境をプローブし、再開可能なセッションがあるか確認
PHASE 1: コンテキスト + 教訓ファイルを読み込む
PHASE 2: 設定を確認し、foreground か background を選ぶ

IF foreground:
  現在の Codex セッションでループを実行
ELSE background:
  autoresearch-launch.json を書き出して detached runtime を開始

共有ループ (永久 or N 回):
  1. 現在の状態 + git 履歴 + 結果ログ + 教訓を確認
  2. 仮説を1つ選択（パースペクティブを適用し、環境でフィルタリング）
     -- 並列モードがアクティブな場合は N 個の仮説を選択
  3. アトミックな変更を1つ実施
  4. git commit（検証の前に）
  5. 機械的検証 + guard を実行
  6. 改善 -> 保持（教訓を抽出）。悪化 -> 承認済みのロールバック戦略。クラッシュ -> 修正またはスキップ。
  7. 結果を記録
  8. ヘルスチェック（ディスク、git、検証の健全性）
  9. 3回以上連続破棄 -> REFINE、5回以上 -> PIVOT、2回の PIVOT -> Web 検索
  10. 繰り返す。決して止めない。決して質問しない。
```

---

## 仕組み

一文で伝えるだけ。あとは Codex が全てやります。

リポジトリをスキャンし、プランを提案し、確認を取り、自律的に反復します：

| あなたの一言 | 何が起こるか |
|-------------|------------|
| "テストカバレッジを上げて" | リポジトリをスキャン、指標を提案、目標達成か中断まで反復 |
| "12個の失敗テストを直して" | 失敗を検出、一つずつ修復してゼロになるまで |
| "なぜAPIが503を返すのか？" | 反証可能な仮説と証拠で根本原因を追跡 |
| "このコードは安全か？" | STRIDE + OWASP監査を実行、全発見にコード証拠付き |
| "リリースして" | リリース準備を検証、チェックリスト生成、ゲート付きリリース |
| "最適化したいが何を測ればいいかわからない" | リポジトリを分析、指標を提案、すぐ使える設定を生成 |

裏側では、Codex があなたの言葉を7つの専門モード
（loop、plan、debug、fix、security、ship、exec）のいずれかにマッピングします。
モードを選ぶ必要はありません -- 目標を述べるだけです。

---

## Codex が自動で把握すること

Codex はあなたの言葉とリポジトリから全てを推論します。設定を書く必要はありません。

| 必要な情報 | 取得方法 | 例 |
|-----------|---------|-----|
| 目標 | あなたの一言 | "全てのany型を除去して" |
| スコープ | リポジトリ構造をスキャン | src/**/*.ts を自動発見 |
| 指標 | 目標 + ツールチェーンから提案 | any カウント（現在: 47） |
| 方向 | "改善" / "削減" / "除去" から推論 | 減少 |
| 検証コマンド | リポジトリのツールとマッチング | grep カウント + tsc --noEmit |
| ガード（任意） | リグレッションリスクがあれば提案 | npm test |

開始前に、Codex は常に検出した内容を提示し、確認を求めます。
最低1ラウンド、最大5ラウンドの確認があります。その後 `foreground` か `background` を選んで "go" と言います。`foreground` では現在のセッション内で反復を続け、`background` では detached runtime に引き継いで席を外せます。
本当に無人で走らせたいなら、Codex CLI の承認 / サンドボックス設定を、`git commit` や `git revert` で止まらないように事前に調整してください。使い捨てのリポジトリや信頼できるリポジトリなら、Codex により広い権限を与えるのが一番簡単です。

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
       - 実行モード：foreground と background のどちらにしますか？
       - ゼロになるまで実行、または N 回の反復で上限を設定？

       実行モードを選び、その後 "go" と返信して開始。

あなた: Background、go。一晩中走らせて。

Codex: background 実行を開始。最初にベースラインを取り、その後 detached iteration に入ります。
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
       - 実行モード：foreground と background のどちらにしますか？
       - ruff でガードして lint の問題を防ぎますか？
       - 全て修正しますか、それとも特定のモジュールに集中しますか？

       実行モードを選び、その後 "go" と返信して開始。

あなた: Foreground、go。全部修正して、ruff でガードして。
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

`exec` を除く全ての反復実行から構造化された教訓が抽出されます -- 何が有効だったか、何が失敗したか、そしてなぜか。教訓は `autoresearch-lessons.md`（結果ログと同様にコミットされない）に保存され、将来の実行開始時に参照されることで、実績のある戦略に仮説生成を偏らせ、既知の行き止まりを回避します。`exec` モードは既存の教訓を読むことはできますが、新規作成や更新は行いません。

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

Codex がインタラクティブモードで以前中断された run を検出した場合、最初からやり直す代わりに最後の一貫した状態から再開できます。主要な回復ソースは `autoresearch-state.json` で、各イテレーションでアトミックに更新されるコンパクトな状態スナップショットです。`exec` モードでは状態は `/tmp/codex-autoresearch-exec/...` 配下の一時ファイルにのみ保持され、`exec` ワークフローが終了前に明示的に削除します。`foreground` は `research-results.tsv` と `autoresearch-state.json` から直接再開します。分離された `background` 実行コントローラが直接再開するには、既存の `autoresearch-launch.json` が引き続き必要です。

回復優先度（インタラクティブモード）：

1. **JSON + TSV 一致、かつ launch manifest が存在：** 即座に再開、ウィザードをスキップ
2. **JSON 有効、TSV 不一致：** ミニウィザード（1 ラウンド確認）
3. **JSON 欠落または破損、TSV 存在：** 補助スクリプトが保持状態を再構築して確認し、その後新しい起動マニフェストで続行
4. **両方なし：** 新規開始（以前の永続的な run-control 工件をアーカイブ）

`references/session-resume-protocol.md` を参照。

---

## CI/CD モード（exec）

自動化パイプライン向けの非対話モード。全ての設定は事前に指定されます -- ウィザードなし、常に上限あり、JSON 出力。

```yaml
# GitHub Actions の例
- name: Autoresearch optimization
  run: |
    codex exec --dangerously-bypass-approvals-and-sandbox <<'PROMPT'
    $codex-autoresearch
    Mode: exec
    Goal: Reduce type errors
    Scope: src/**/*.ts
    Metric: type error count
    Direction: lower
    Verify: tsc --noEmit 2>&1 | grep -c error
    Iterations: 20
    PROMPT
```

終了コード：0 = 改善、1 = 改善なし、2 = ハードブロッカー。

CI で `codex exec` を使う前に、Codex CLI の認証を事前に設定してください。制御された自動化環境では、単独の `exec` 実行も managed runtime の既定ポリシー `danger_full_access` に揃うよう、`codex exec --dangerously-bypass-approvals-and-sandbox ...` を優先してください。プログラム実行では API key 認証が推奨です。

`Mode: exec` を skill 同梱の helper script で動かす場合、repo 直下の古い成果物を手動でリネームしないでください。`autoresearch_init_run.py --mode exec ...` が既定の `research-results.tsv` と `autoresearch-state.json` を `research-results.prev.tsv` と `autoresearch-state.prev.json` に自動で退避してから、新しい実行を初期化します。

詳細は `references/exec-workflow.md` を参照。

---

## 結果ログ

各イテレーションは 2 つの補完的な形式で記録されます：

- **`research-results.tsv`** -- 完全な監査証跡。各イテレーションは 1 つの主行で表し、必要に応じて並列 worker 行を追加
- **`autoresearch-state.json`** -- インタラクティブモードでの高速セッション再開用のコンパクトな状態スナップショット

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

`exec` モードでは状態スナップショットは `/tmp/codex-autoresearch-exec/...` の一時領域にのみ存在し、`exec` ワークフローが終了前に明示的に削除します。これらのアーティファクトは `<skill-root>/scripts/...` 配下の bundled helper scripts で更新し、対象リポジトリ自身の `scripts/` ディレクトリは使わないでください。

両方のファイルは git にコミットしません。セッション再開時、JSON 状態は TSV の主イテレーション要約とクロスバリデーションされ、不整合を検出します。生の行数そのものは判定基準にしません。進捗サマリーは 5 イテレーションごとに出力されます。有界実行では最後にベースラインから最良値までのサマリーが出力されます。

これらの状態成果物は `<skill-root>/scripts/...` 配下の helper scripts で管理されますが、ほとんどのユーザーは引き続き唯一の人間向け入口である **`$codex-autoresearch`** だけを使えば十分です。ここで `<skill-root>` は読み込まれている `SKILL.md` のあるディレクトリを指し、一般的な repo-local インストールでは `.agents/skills/codex-autoresearch` です。

control-plane をスクリプト化したりデバッグしたりする場合、repo 基準の helper は通常 `--repo <repo>` を優先して使います。次の形を推奨します。

- `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_launch_gate.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`

`--results-path`、`--state-path`、`--launch-path`、`--runtime-path` は上級向け override として引き続き利用できます。`autoresearch_resume_prompt.py` と `autoresearch_supervisor_status.py` を直接呼ぶ場合も、同じ repo-first 規約です。

人間向けの公開入口は、いまは **`$codex-autoresearch`** ひとつだけです。

- 最初の対話実行では、目標を自然に説明し、確認の質問に答え、`foreground` か `background` を明示的に選んでから `go` と返します
- `foreground` では Codex は現在のセッション内に残り、そのまま反復を続けます。作られるのは `research-results.tsv`、`autoresearch-state.json`、lessons だけです
- `background` では Codex は `autoresearch-launch.json` を書き込み、切り離された実行コントローラを自動で起動します
- `foreground` と `background` は同じ loop プロトコル、metric の意味、repo/scope ルールを共有しますが、同じ repo/run に対しては排他的です。同じ primary repo の artifacts に対して両方を同時に走らせないでください
- 後から同じ interactive run を別のモードで続けたい場合でも、入口は同じ `$codex-autoresearch` のままです。続行前に、skill が内部で共有 state を選んだモードへ同期し、background `start` も同じ同期を自動で行います
- 単一リポジトリの実行は引き続きデフォルトです。この場合、宣言した scope は run-control 工程を保持する primary repo にだけ適用されます
- 実験が複数リポジトリにまたがる場合、確認済みの launch manifest には companion repos と各 repo 固有の scope も記述できます。runtime preflight は管理対象の全 repo を検査しますが、`research-results.tsv`、`autoresearch-state.json`、runtime-control の各工件は primary repo に置かれたままです
- このモデルでは TSV の `commit` 列は引き続き primary repo の commit だけを記録し、companion repo ごとの commit provenance は `autoresearch-state.json` に保存されます
- `background` の各 managed runtime cycle は、runtime prompt を stdin で渡した非対話の `codex exec` セッションとして実行されます
- `execution_policy` はネストした Codex セッションを起動する経路、つまり `background` と `exec` にだけ適用されます。この skill の既定値は `danger_full_access` です
- その後の `status`、`stop`、`resume` も同じ `$codex-autoresearch` から行いますが、`status/stop` は `background` にだけ適用されます
- `Mode: exec` は、CI や完全に指定された自動化向けの上級パスとして残ります

スクリプト実行や実行系のデバッグ向けに、直接制御コマンドも利用できます。

- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`


---

## セキュリティモデル

| 懸念事項 | 対処方法 |
|----------|----------|
| ダーティなワークツリー | runtime の事前チェックが、対象範囲外の変更をクリーンアップまたは隔離するまで起動と再起動をブロック |
| 失敗した変更 | 起動前に承認されたロールバック戦略を使用。隔離された実験ブランチ/ワークツリーで承認済みなら `git reset --hard HEAD~1`、それ以外は `git revert --no-edit HEAD`。結果ログが監査証跡 |
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
| コンテキストドリフト（長時間実行） | 10 イテレーションごとにプロトコルフィンガープリントチェック。compaction 後は頻度を上げ、失敗時はディスクから再読み込み |

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
    validate_skill_structure.sh     # structure validator
    autoresearch_helpers.py         # TSV / JSON / runtime を扱う共通ヘルパー
    autoresearch_launch_gate.py     # 起動前に fresh / resumable / needs_human を判定
    autoresearch_resume_prompt.py   # 保存済み設定から runtime 管理用のプロンプトを組み立てる
    autoresearch_runtime_ctl.py     # runtime の launch / create-launch / start / status / stop を制御
    autoresearch_commit_gate.py     # git / artifact / rollback gate
    autoresearch_decision.py        # structured keep / discard / crash policy helpers
    autoresearch_health_check.py    # executable health checks
    autoresearch_lessons.py         # structured lessons append / list helpers
    autoresearch_init_run.py        # initialize baseline log + state
    autoresearch_record_iteration.py # append one main iteration + update state
    autoresearch_resume_check.py    # decide full_resume / mini_wizard / fallback
    autoresearch_select_parallel_batch.py # log worker rows + batch winner
    autoresearch_exec_state.py      # resolve / cleanup exec scratch state
    autoresearch_supervisor_status.py # decide relaunch / stop / needs_human
    check_skill_invariants.py       # validate real skill-run artifacts
    run_skill_e2e.sh                # disposable Codex CLI smoke harness
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

**実行間で学習する？** はい。教訓は各 `keep`、各 `pivot`、そして最近の教訓がないまま管理対象の実行が終了した時に抽出されます。教訓ファイルはセッション間で保持されます。`exec` は既存の教訓を読むだけで、新しい教訓は書き込みません。

**中断後に再開できる？** はい。`foreground` は `research-results.tsv` と `autoresearch-state.json` から再開します。`background` ではそれに加えて `autoresearch-launch.json` も必要です。確認済みの launch state がない場合は、通常の `background` launch フローから新しく開始してください。

**Web 検索は可能？** はい。複数回の戦略ピボット後にスタックした場合に使用されます。Web 検索結果は仮説として扱われ、機械的に検証されます。

**CI で使うには？** `Mode: exec` または `codex exec` を使用してください。制御された自動化環境では、既定 runtime と権限を揃えるため `codex exec --dangerously-bypass-approvals-and-sandbox ...` を使うのが推奨です。全ての設定は事前に指定され、出力は JSON 形式で、終了コードが成功/失敗を示します。

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
