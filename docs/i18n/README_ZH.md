<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>瞄准。迭代。抵达。</b></h2>

<p align="center">
  <i>Codex 的自主目标驱动实验引擎。</i>
</p>

<p align="center">
  <a href="https://developers.openai.com/codex/skills"><img src="https://img.shields.io/badge/Codex-Skill-blue?logo=openai&logoColor=white" alt="Codex Skill"></a>
  <a href="https://github.com/leo-lilinxiao/codex-autoresearch"><img src="https://img.shields.io/github/stars/leo-lilinxiao/codex-autoresearch?style=social" alt="GitHub Stars"></a>
  <a href="../../LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
</p>

<p align="center">
  <a href="../../README.md">English</a> ·
  <b>🇨🇳 中文</b> ·
  <a href="README_JA.md">🇯🇵 日本語</a> ·
  <a href="README_KO.md">🇰🇷 한국어</a> ·
  <a href="README_FR.md">🇫🇷 Français</a> ·
  <a href="README_DE.md">🇩🇪 Deutsch</a> ·
  <a href="README_ES.md">🇪🇸 Español</a> ·
  <a href="README_PT.md">🇧🇷 Português</a> ·
  <a href="README_RU.md">🇷🇺 Русский</a>
</p>

<p align="center">
  <a href="#快速上手">快速上手</a> ·
  <a href="#它做什么">它做什么</a> ·
  <a href="#架构">架构</a> ·
  <a href="#工作原理">工作原理</a> ·
  <a href="#codex-自动推断的内容">配置</a> ·
  <a href="#跨运行学习">学习</a> ·
  <a href="#并行实验">并行</a> ·
  <a href="../GUIDE.md">操作手册</a> ·
  <a href="../EXAMPLES.md">配方集</a>
</p>

---

## 快速上手

**1. 安装：**

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

或在 Codex 中使用 skill installer：
```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

**2. 在项目中打开 Codex，说出你想做的事：**

```text
$codex-autoresearch
把 TypeScript 代码里所有的 any 类型都消除掉
```

**3. Codex 扫描、确认，然后自主迭代：**

```
Codex: 在 src/**/*.ts 中找到 47 个 `any`。

       已确认：
       - 目标：消除 src/**/*.ts 中所有 any 类型
       - 指标：any 出现次数（当前 47），方向：降低
       - 验证：grep 计数 + tsc --noEmit 守护

       还需确认：
       - 跑到全部消除，还是限制在 N 次迭代？

       回复 "go" 开始，或告诉我要改什么。

你:    go，跑一晚上。

Codex: 开始 -- 基线：47。持续迭代直到你中断。
```

改善累积，失败回滚，全程记录。

更多安装方式见 [INSTALL.md](../INSTALL.md)。完整操作手册见 [GUIDE.md](../GUIDE.md)。

---

## 它做什么

一个 Codex skill，在你的代码库上运行 "修改-验证-决策" 循环。每次迭代做一个原子改动，用机械化指标验证，然后保留或丢弃。进展累积在 git 中；失败自动回滚。适用于任何语言、任何框架、任何可测量的目标。

灵感来自 [Karpathy 的 autoresearch](https://github.com/karpathy/autoresearch) 原则，推广到 ML 之外的所有领域。

### 为什么做这个

Karpathy 的 autoresearch 证明了一个简单的循环 -- 修改、验证、保留或丢弃、重复 -- 就能在一夜之间把 ML 训练从基线推进到新高。codex-autoresearch 把这个循环泛化到软件工程中一切有数字的场景。测试覆盖率、类型错误、性能延迟、lint 警告 -- 只要有指标，就能自主迭代。

---

## 架构

```
              +---------------------+
              |     环境探测        |  <-- Phase 0: 检测 CPU/GPU/RAM/工具链
              +---------+-----------+
                        |
              +---------v-----------+
              |    会话恢复?        |  <-- 检查先前运行的产物
              +---------+-----------+
                        |
              +---------v-----------+
              |    读取上下文       |  <-- 读取范围 + 经验文件
              +---------+-----------+
                        |
              +---------v-----------+
              |    建立基线         |  <-- iteration #0
              +---------+-----------+
                        |
         +--------------v--------------+
         |                             |
         |  +----------------------+   |
         |  |    选择假设           |   |  <-- 参考经验 + 多视角推理
         |  | (或 N 个并行)        |   |      按环境过滤
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  |   做一次修改         |   |
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
         |        改善了?              |
         |       /         \           |
         |     yes          no         |
         |     /              \        |
         |  +-v------+   +----v-----+ |
         |  |  KEEP  |   | REVERT   | |
         |  |+lesson |   +----+-----+ |
         |  +--+-----+        |       |
         |      \            /         |
         |   +--v----------v---+      |
         |   |   记录结果       |      |
         |   +--------+--------+      |
         |            |               |
         |   +--------v--------+      |
         |   |   健康检查       |      |  <-- 磁盘、git、验证命令健康
         |   +--------+--------+      |
         |            |               |
         |     3+ 次丢弃?             |
         |    /             \         |
         |  no              yes       |
         |  |          +----v-----+   |
         |  |          | REFINE / |   |  <-- pivot 协议升级
         |  |          | PIVOT    |   |
         |  |          +----+-----+   |
         |  |               |         |
         +--+------+--------+         |
         |         (重复)             |
         +----------------------------+
```

循环持续运行直到中断（无界）或恰好 N 次迭代（通过 `Iterations: N` 设定上限）。

**伪代码：**

```
PHASE 0: 探测环境，检查是否有可恢复的会话
PHASE 1: 读取上下文 + 经验文件

LOOP (永远 or N 次):
  1. 审视当前状态 + git 历史 + 结果日志 + 经验
  2. 选一个假设（应用多视角推理，按环境过滤）
     -- 并行模式激活时选 N 个假设
  3. 做一个原子改动
  4. git commit（验证之前）
  5. 运行机械化验证 + guard
  6. 改善了 -> 保留（提取经验）。变差了 -> git reset。崩溃了 -> 修复或跳过。
  7. 记录结果
  8. 健康检查（磁盘、git、验证健康状态）
  9. 连续 3 次丢弃 -> REFINE；5 次 -> PIVOT；2 次 PIVOT -> Web 搜索
  10. 重复。绝不停止。绝不提问。
```

---

## 工作原理

你说一句话，Codex 搞定一切。

它扫描你的仓库，提出方案，向你确认，然后自主迭代：

| 你说的话 | 发生了什么 |
|---------|-----------|
| "提升我的测试覆盖率" | 扫描仓库，提出指标，持续迭代直到目标达成或被中断 |
| "修复那 12 个失败的测试" | 检测失败，逐个修复直到全部通过 |
| "为什么 API 返回 503？" | 用可证伪的假设和证据追踪根因 |
| "这段代码安全吗？" | 运行 STRIDE + OWASP 审计，每个发现都有代码证据 |
| "准备发布" | 验证就绪状态，生成检查清单，门控发布 |
| "我想优化但不知道该测量什么" | 分析仓库，建议指标，生成可直接使用的配置 |

在幕后，Codex 将你的话映射到 7 个专用模式之一
（loop、plan、debug、fix、security、ship、exec）。你不需要选择模式 --
只需描述你的目标。

---

## Codex 自动推断的内容

Codex 从你的话和你的仓库中推断一切。你不需要编写任何配置。

| 它需要什么 | 如何获取 | 示例 |
|-----------|---------|------|
| 目标 | 你说的话 | "消除所有 any 类型" |
| 范围 | 扫描仓库结构 | 自动发现 src/**/*.ts |
| 指标 | 基于目标 + 工具链提出 | any 计数（当前：47） |
| 方向 | 从 "改善" / "减少" / "消除" 推断 | 降低 |
| 验证命令 | 匹配仓库工具链 | grep 计数 + tsc --noEmit |
| 守护（可选） | 如果存在回归风险则建议 | npm test |

开始之前，Codex 总是向你展示它发现的内容并请求确认。
最少一轮确认，最多五轮。然后你先选 `foreground` 或 `background`，再说 "go"。`foreground` 会在当前会话里继续迭代，`background` 会交给 detached runtime，让你可以离开。
如果你想真正无人值守地跑起来，需要提前把 Codex CLI 的审批 / 沙箱权限配置到不会打断 `git commit` 或 `git revert`。在一次性或可信仓库里，直接给 Codex 更高权限是最简单的做法。

### 双门验证

两个命令各有分工：

- **Verify** = "目标指标改善了吗？"（衡量进展）
- **Guard** = "其他东西没坏吧？"（防止回归）

```text
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'   # 覆盖率提升了吗？
Guard: npx tsc --noEmit                                                              # 类型还过吗？
```

如果 verify 通过但 guard 失败，改动会被重新调整（最多 2 次），然后回滚。Guard 涉及的文件永不被修改。

---

## 模式详情

### loop

默认模式。迭代优化一个可测量的目标。

```
你:    把 TypeScript 代码里所有的 any 类型都消除掉

Codex: 在 src/**/*.ts 中找到 47 个 `any`。

       已确认：
       - 目标：消除所有 any 类型
       - 指标：any 出现次数（当前 47），方向：降低
       - 验证：grep 计数，守护：tsc --noEmit

       还需确认：
       - 运行模式：foreground 还是 background？
       - 跑到归零，还是限制在 N 次迭代？

       先选运行模式，再回复 "go" 开始。

你:    Background，go。跑一晚上。

Codex: 开始后台运行。先建立基线，然后进入 detached iterations。
```

### plan

将模糊目标转化为经过验证的循环配置。

```
你:    我想让 API 更快，但不知道从哪下手

Codex: 扫描了仓库。API 层在 src/api/，用的 Express + Prisma。

       还需确认：
       - 更在意 p95 延迟、吞吐量还是冷启动？
       - 测整个 API 还是特定接口？

       告诉我你的优先级。

你:    p95 延迟，/search 接口最慢。
```

### debug

证据驱动的 bug 猎杀。每次迭代测试一个可证伪的假设。

```
你:    API 在高并发下偶尔返回 503，不知道为什么

Codex: 我看到 src/db/pool.ts 有连接池，src/middleware/ 有限流，
       还有 3 个异步处理器没有错误边界。

       已确认：
       - 症状：并发负载下间歇性 503
       - 范围：src/api/、src/db/、src/middleware/

       还需确认：
       - 什么时候开始的？某次改动之后还是一直都有？
       - 找到原因后要直接修吗？

       告诉我上下文。

你:    上周连接池重构后开始的。先找原因。
```

### fix

迭代修复错误直到计数归零。

```
你:    重构后 pytest 挂了 12 个测试

Codex: 看到 tests/ 里有 12 个失败。

       已确认：
       - 目标：让所有 pytest 测试通过
       - 当前：12 个失败

       还需确认：
       - 运行模式：foreground 还是 background？
       - 要同时用 ruff 守护避免引入 lint 问题吗？
       - 全部修还是先集中某个模块？

       先选运行模式，再回复 "go" 开始。

你:    Foreground，go。全部修，用 ruff 守护。
```

### security

只读的 STRIDE + OWASP + 红队审计。每个发现必须有代码证据。

```
你:    检查一下 API 有没有注入漏洞

Codex: 已确认：
       - 范围：src/api/ 和 src/middleware/（14 个文件）
       - 重点：SQL 注入、XSS、输入验证

       还需确认：
       - 只出报告，还是顺便修掉严重问题？
       - 要不要也覆盖认证/权限控制？

       告诉我偏好。

你:    先出报告，认证也看一下。
```

### ship

门控发布验证。自动检测你要发布什么（PR、部署、发版）。

```
你:    发布吧

Codex: 检测到：PR 到 main，3 个 commit。

       已确认：
       - 类型：代码 PR
       - 目标：main 分支

       还需确认：
       - 先演练还是直接发？
       - 发布后监控多久？（5 分钟 / 15 分钟 / 跳过）

       告诉我偏好。

你:    先演练。
```

各模式的详细用法和高级选项见 [GUIDE.md](../GUIDE.md)。

---

## 模式组合

模式可以顺序组合：

```
plan  -->  loop              # 先生成配置，再执行
debug -->  fix               # 先找 bug，再修复
security + fix               # 审计并修复一步到位
```

---

## 跨运行学习

除 `exec` 外的每次迭代运行结束后提取结构化经验 -- 什么有效、什么失败、为什么。经验持久保存在 `autoresearch-lessons.md`（不提交，类似结果日志），并在未来运行启动时参考，使假设生成偏向已验证的策略，避开已知的死胡同。`exec` 模式可以读取已有经验，但不会创建或更新它。

- 每次保留迭代后提取正面经验
- 每次 PIVOT 决策后提取策略经验
- 运行结束时提取总结经验
- 容量：最多 50 条，旧条目按时间衰减汇总

详见 `references/lessons-protocol.md`。

---

## 智能卡住恢复

循环使用分级升级系统替代盲目重试：

| 触发条件 | 动作 |
|---------|------|
| 连续 3 次丢弃 | **REFINE** -- 在当前策略内调整 |
| 连续 5 次丢弃 | **PIVOT** -- 放弃策略，尝试根本不同的方法 |
| 2 次 PIVOT 无改善 | **Web 搜索** -- 寻找外部解决方案 |
| 3 次 PIVOT 无改善 | **软阻塞** -- 警告并继续更大胆的尝试 |

一次成功的保留即重置所有计数器。详见 `references/pivot-protocol.md`。

---

## 并行实验

使用子代理工作者在隔离的 git worktree 中同时测试多个假设：

```
编排器（主代理）
  +-- 工作者 A (worktree-a) -> 假设 1
  +-- 工作者 B (worktree-b) -> 假设 2
  +-- 工作者 C (worktree-c) -> 假设 3
```

编排器选择最佳结果，合并它，丢弃其余。在向导阶段回答"是"启用并行实验。如果不支持 worktree 则回退到串行模式。

详见 `references/parallel-experiments-protocol.md`。

---

## 会话恢复

如果 Codex 在交互模式下检测到之前被中断的运行，它可以从最后一致的状态恢复，而不是从头开始。主要恢复来源是 `autoresearch-state.json`，一个每次迭代原子更新的紧凑状态快照。`exec` 模式下，状态只会写入 `/tmp/codex-autoresearch-exec/...` 下的临时文件，并需要由 `exec` 工作流在退出前显式清理。foreground 恢复只依赖 `research-results.tsv` 和 `autoresearch-state.json`；要让分离的 background 运行控制器直接恢复，仍然必须已经存在 `autoresearch-launch.json`。

恢复优先级（交互模式）：

1. **JSON + TSV 一致，且启动清单存在：** 立即恢复，跳过向导
2. **JSON 有效，TSV 不一致：** 迷你向导（1 轮确认）
3. **JSON 缺失或损坏，TSV 存在：** 辅助脚本先重建保留状态供确认，然后用新的启动清单继续
4. **都不存在：** 全新开始（归档之前的持久 run-control 工件）

参见 `references/session-resume-protocol.md`。

---

## CI/CD 模式 (exec)

用于自动化流水线的非交互模式。所有配置预先提供 -- 无向导，始终有界，JSON 输出。

```yaml
# GitHub Actions 示例
- name: Autoresearch 优化
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

退出码：0 = 已改善，1 = 无改善，2 = 硬阻塞。

在 CI 中使用 `codex exec` 前，请先配置好 Codex CLI 认证。在受控自动化环境里，建议优先使用 `codex exec --dangerously-bypass-approvals-and-sandbox ...`，这样独立 `exec` 运行会与托管 runtime 默认的 `danger_full_access` 策略保持一致。对于程序化运行，优先使用 API key 认证。

如果 `Mode: exec` 由 skill 自带的 helper scripts 驱动，不要先手工重命名 repo 根目录中的旧工件。`autoresearch_init_run.py --mode exec ...` 会自动把默认的 `research-results.tsv` 和 `autoresearch-state.json` 归档为 `research-results.prev.tsv` 和 `autoresearch-state.prev.json`，然后再初始化新的执行。

详见 `references/exec-workflow.md`。

---

## 结果日志

每次迭代以两种互补格式记录：

- **`research-results.tsv`** -- 完整审计跟踪，每次迭代一个主行，必要时附带并行 worker 行
- **`autoresearch-state.json`** -- 用于交互模式快速会话恢复的紧凑状态快照

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

`exec` 模式下，状态快照仅保存在 `/tmp/codex-autoresearch-exec/...` 的临时位置，并需要由 `exec` 工作流在退出前显式清理。请通过 `<skill-root>/scripts/...` 下随 skill 打包的 helper scripts 更新这些工件，而不是调用目标仓库自己的 `scripts/` 目录。

两个文件都不提交到 git。会话恢复时，JSON 状态会与重建出的 TSV 主迭代摘要交叉验证，而不是直接对比行数。进度摘要每 5 次迭代打印一次。有界运行在最后打印基线到最优的总结。

这些状态工件虽然由随 skill 打包的 helper scripts 在 `<skill-root>/scripts/...` 下维护，但大多数用户仍然只需要使用唯一的人类入口：**`$codex-autoresearch`**。这里 `<skill-root>` 指当前加载的 `SKILL.md` 所在目录；常见的 repo-local 安装位置是 `.agents/skills/codex-autoresearch`。

如果你是在做脚本化调用或调试 control-plane，则以 repo 为锚点的 helper 默认优先使用 `--repo <repo>`。例如：

- `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_launch_gate.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`

`--results-path`、`--state-path`、`--launch-path`、`--runtime-path` 仍然保留为高级 override；`autoresearch_resume_prompt.py` 和 `autoresearch_supervisor_status.py` 直接调用时也遵循同样的 repo-first 约定。

对人类用户来说，现在只保留一个主要入口：**`$codex-autoresearch`**。

- 首次交互运行：自然描述目标，回答确认问题，明确选择 `foreground` 或 `background`，然后回复 `go`
- 如果选择 `foreground`，Codex 会留在当前会话里持续迭代，只写 `research-results.tsv`、`autoresearch-state.json` 和 lessons，不会创建 launch/runtime 控制文件
- 如果选择 `background`，Codex 会写入 `autoresearch-launch.json` 并启动分离的运行控制器
- `foreground` 和 `background` 共享同一套 loop 协议、指标语义以及 repo/scope 规则，但对同一个 repo/run 来说它们是互斥的；不要同时让两种模式写同一套主仓工件
- 如果之后想把同一个交互 run 切到另一种模式，仍然通过同一个 `$codex-autoresearch` 入口继续；继续之前，skill 会在内部先把共享 state 同步到目标模式，background `start` 也会自动完成同样的同步
- 单仓运行仍然是默认形态；此时声明的 scope 只作用于承载 run-control 工件的主仓库
- 如果实验跨多个仓库，确认后的 launch manifest 也可以声明 companion repos，并为每个仓库单独给出 scope。runtime preflight 会检查所有托管仓库，但 `research-results.tsv`、`autoresearch-state.json` 以及 runtime-control 工件仍然锚定在主仓库
- 在这种模型下，TSV 的 `commit` 列仍然只记录主仓库提交；companion repo 的逐仓 commit provenance 则记录在 `autoresearch-state.json` 中
- 之后每个 background 托管循环都会启动一个非交互式 `codex exec` 会话，并通过 stdin 传入 runtime prompt
- `execution_policy` 只作用于会再拉起嵌套 Codex 会话的路径，也就是 background 托管循环和 `exec`；当前 skill 默认是 `danger_full_access`
- 之后如果想看状态、停止、恢复，仍然通过 `$codex-autoresearch` 这个 skill 来做；其中 `status/stop` 只适用于 background 运行
- `Mode: exec` 仍然保留给 CI / 高级自动化

如果你在做后端自动化或调试运行控制面，也可以直接调用：

- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`


---

## 安全模型

| 问题 | 处理方式 |
|------|---------|
| 脏工作树 | runtime 预检会阻止启动或重启，直到范围外变更被清理或隔离 |
| 失败的更改 | 使用启动前确认过的回滚策略：隔离实验分支/工作树中可用已批准的 `git reset --hard HEAD~1`，否则使用 `git revert --no-edit HEAD`；结果日志仍是审计记录 |
| 守护失败 | 最多 2 次修复尝试后丢弃 |
| 语法错误 | 立即自动修复，不计入迭代 |
| 运行时崩溃 | 最多 3 次修复尝试，然后跳过 |
| 资源耗尽 | 回滚，尝试更小的变体 |
| 挂起进程 | 超时后终止，回滚 |
| 卡住 (3+ 次丢弃) | REFINE 策略；5+ 次 -> PIVOT 新方法；升级到 Web 搜索 |
| 循环中的歧义 | 自主应用最佳实践；永不暂停询问用户 |
| 外部副作用 | ship 模式需要在预启动向导阶段明确确认 |
| 环境限制 | 启动时探测；自动过滤不可行的假设 |
| 中断的会话 | 下次调用时从最后一致状态恢复 |
| 上下文漂移（长时间运行） | 每 10 次迭代执行协议指纹检查；发生压缩后提高检查频率；失败时从磁盘重新读取 |

---

## 项目结构

```
codex-autoresearch/
  SKILL.md                          # skill 入口（Codex 加载）
  README.md                         # 英文文档
  CONTRIBUTING.md                   # 贡献指南
  LICENSE                           # MIT
  agents/
    openai.yaml                     # Codex UI 元数据
  image/
    banner.png                      # 项目 banner
  docs/
    INSTALL.md                      # 安装指南
    GUIDE.md                        # 操作手册
    EXAMPLES.md                     # 按领域分类的配方集
    i18n/
      README_ZH.md                  # 本文件
      README_JA.md                  # 日语
      README_KO.md                  # 韩语
      README_FR.md                  # 法语
      README_DE.md                  # 德语
      README_ES.md                  # 西班牙语
      README_PT.md                  # 葡萄牙语
      README_RU.md                  # 俄语
  scripts/
    validate_skill_structure.sh     # 结构验证脚本
    autoresearch_helpers.py         # 共享 TSV / JSON / runtime 工具脚本
    autoresearch_launch_gate.py     # 在启动前判断 fresh / resumable / needs_human
    autoresearch_resume_prompt.py   # 从启动清单生成运行控制器使用的提示词
    autoresearch_runtime_ctl.py     # 控制 launch / create-launch / start / status / stop
    autoresearch_commit_gate.py     # git / artifact / rollback gate
    autoresearch_decision.py        # 结构化 keep / discard / crash 决策
    autoresearch_health_check.py    # 可执行 health check
    autoresearch_lessons.py         # lessons 追加 / 列表
    autoresearch_init_run.py        # 初始化基线日志与状态
    autoresearch_record_iteration.py # 追加一次主迭代并更新状态
    autoresearch_resume_check.py    # 判断 full_resume / mini_wizard / fallback
    autoresearch_select_parallel_batch.py # 记录 worker 行并选出胜者
    autoresearch_exec_state.py      # 解析 / 清理 exec scratch state
    autoresearch_supervisor_status.py # 判断 relaunch / stop / needs_human
    check_skill_invariants.py       # 校验真实 skill 运行产物
    run_skill_e2e.sh                # 一次性 Codex CLI 冒烟 harness
  references/
    core-principles.md              # 通用原则
    autonomous-loop-protocol.md     # 循环协议规范
    plan-workflow.md                # plan 模式规范
    debug-workflow.md               # debug 模式规范
    fix-workflow.md                 # fix 模式规范
    security-workflow.md            # security 模式规范
    ship-workflow.md                # ship 模式规范
    exec-workflow.md                # CI/CD 非交互模式规范
    interaction-wizard.md           # 交互式设置契约
    structured-output-spec.md       # 输出格式规范
    modes.md                        # 模式索引
    results-logging.md              # TSV 格式规范
    lessons-protocol.md             # 跨运行学习
    pivot-protocol.md               # 智能卡住恢复（PIVOT/REFINE）
    web-search-protocol.md          # 卡住时的网络搜索
    environment-awareness.md        # 硬件/资源检测
    parallel-experiments-protocol.md # 子代理并行测试
    session-resume-protocol.md      # 中断运行恢复
    health-check-protocol.md        # 自我监控
    hypothesis-perspectives.md      # 多视角假设推理
```

---

## FAQ

**如何选指标？** 用 `Mode: plan`，它会分析代码库并建议。

**支持什么语言？** 全部。协议与语言无关，只有验证命令是领域特定的。

**怎么停止？** 中断 Codex，或设置 `Iterations: N`。git 状态始终一致，因为提交在验证之前。

**security 模式会改代码吗？** 不会。只读分析。在设置阶段告诉 Codex "也修掉严重问题" 即可选择性修复。

**迭代多少次？** 取决于任务。定向修复 5 次，探索性 10-20 次，过夜运行不设限。

**它会跨运行学习吗？** 是的。每次 `keep`、每次 `pivot`，以及受管运行结束且最近 5 次迭代没有新经验时，都会提取经验。经验文件跨会话持久保存；`exec` 只读取已有经验，不写入新经验。

**中断后能恢复吗？** 可以。foreground 运行从 `research-results.tsv` 和 `autoresearch-state.json` 恢复；background 运行还需要已有的 `autoresearch-launch.json`。缺少已确认 launch state 时，应按正常 background 启动流程重新开始。

**它能搜索网络吗？** 是的，在多次策略转向后仍然卡住时。搜索结果作为假设处理，机械验证后才应用。

**如何在 CI 中使用？** 使用 `Mode: exec` 或 `codex exec`。在受控自动化环境里，建议使用 `codex exec --dangerously-bypass-approvals-and-sandbox ...`，这样与默认 runtime 权限一致。所有配置预先提供，输出为 JSON，退出码表示成功/失败。

**能同时测试多个想法吗？** 是的。在设置阶段启用并行实验。它使用 git worktree 同时测试最多 3 个假设。

---

## 致谢

本项目基于 [Karpathy 的 autoresearch](https://github.com/karpathy/autoresearch) 的理念构建。Codex skills 平台由 [OpenAI](https://openai.com) 提供。

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

## 许可证

MIT -- 见 [LICENSE](../../LICENSE)。
