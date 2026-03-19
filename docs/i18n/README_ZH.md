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
  <a href="#模式">模式</a> ·
  <a href="#配置">配置</a> ·
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

## 模式

七种模式，统一调用方式：`$codex-autoresearch` 后跟一句自然语言。Codex 自动检测模式并通过对话引导补全配置。

| 模式 | 适用场景 | 何时停止 |
|------|----------|----------|
| `loop` | 有可测量的优化目标 | 中断或 N 次迭代 |
| `plan` | 有目标但不确定配置 | 生成配置块 |
| `debug` | 需要带证据的根因分析 | 所有假设已测试或 N 次迭代 |
| `fix` | 有东西坏了需要修复 | 错误数归零 |
| `security` | 需要结构化漏洞审计 | 所有攻击面已覆盖或 N 次迭代 |
| `ship` | 需要有门控的发布验证 | 所有检查项通过 |
| `exec` | CI/CD 流水线，无人交互 | N 次迭代（必须有界）、JSON 输出 |

**快速选择：**

```
"我要优化 X"              -->  loop（指标不确定就用 plan）
"有东西坏了"              -->  fix（原因不明就用 debug）
"这段代码安全吗？"        -->  security
"准备发布"                -->  ship
codex exec --skill ...          -->  exec  (CI/CD，无需向导)
```

---

## 配置

### 必填字段（loop 模式）

| 字段 | 类型 | 示例 |
|------|------|------|
| `Goal` | 目标描述 | `Reduce type errors to zero` |
| `Scope` | 可修改的文件 glob | `src/**/*.ts` |
| `Metric` | 追踪的数值 | `type error count` |
| `Direction` | `higher` 或 `lower` | `lower` |
| `Verify` | 输出指标的命令 | `tsc --noEmit 2>&1 \| wc -l` |

### 可选字段

| 字段 | 默认值 | 用途 |
|------|--------|------|
| `Guard` | 无 | 防回归的安全命令 |
| `Iterations` | 无限 | 限制为 N 次迭代 |
| `Run tag` | 自动 | 本次运行的标签 |
| `Stop condition` | 无 | 自定义提前停止规则 |

缺少必填字段时，交互式向导会扫描仓库并一定先向你确认再启动（最多 5 轮）。你不需要知道任何字段名。

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

## 快速决策指南

| 你想要... | 模式 | 关键配置 |
|-----------|------|----------|
| 整晚把一个指标往一个方向推 | `loop` | Goal + Metric + Verify |
| 弄清楚该追踪哪个指标 | `plan` | 只需一个 Goal |
| 找出某个东西为什么坏了 | `debug` | Scope + Symptom |
| 让失败的测试/类型/lint 通过 | `fix` | Target 命令 |
| 审计代码中的漏洞 | `security` | Scope + Focus |
| 有信心地发布 | `ship` | 说 "发布吧" 或 "先演练" |
| 在 CI/CD 中无人值守运行 | `exec` | 所有字段预先提供 + Iterations |

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
       - 跑到归零，还是限制在 N 次迭代？

       回复 "go" 开始。

你:    go，跑一晚上。
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
       - 要同时用 ruff 守护避免引入 lint 问题吗？
       - 全部修还是先集中某个模块？

       回复 "go" 开始。

你:    全部修，用 ruff 守护。Go。
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

每次运行结束后提取结构化经验 -- 什么有效、什么失败、为什么。经验持久保存在 `autoresearch-lessons.md`（不提交，类似结果日志），并在未来运行启动时参考，使假设生成偏向已验证的策略，避开已知的死胡同。

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

如果 Codex 检测到先前被中断的运行（结果日志、经验文件、实验提交），它可以从最后一致的状态恢复，而不是从头开始：

- **状态一致：** 立即恢复，跳过向导
- **部分一致：** 迷你向导（1 轮）重新确认
- **不一致或目标不同：** 全新开始（旧日志重命名）

详见 `references/session-resume-protocol.md`。

---

## CI/CD 模式 (exec)

用于自动化流水线的非交互模式。所有配置预先提供 -- 无向导，始终有界，JSON 输出。

```yaml
# GitHub Actions 示例
- name: Autoresearch 优化
  run: codex exec --skill codex-autoresearch
         --goal "减少类型错误" --scope "src/**/*.ts"
         --metric "类型错误数量" --direction lower
         --verify "tsc --noEmit 2>&1 | grep -c error"
         --iterations 20
```

退出码：0 = 已改善，1 = 无改善，2 = 硬阻塞。

详见 `references/exec-workflow.md`。

---

## 结果日志

每次迭代记录到 TSV 文件（`research-results.tsv`）：

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

每 5 次迭代打印进度总结。有界运行结束时打印基线到最佳值的总结。

---

## 安全模型

| 问题 | 处理方式 |
|------|---------|
| 脏工作树 | 拒绝启动；建议使用 plan 模式或干净分支 |
| 失败的更改 | `git reset --hard HEAD~1` 保持历史干净；结果日志是审计记录 |
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

**它会跨运行学习吗？** 是的。每次运行后提取经验，并在下次运行开始时参考。经验文件跨会话持久保存。

**中断后能恢复吗？** 是的。下次调用时，它会检测先前的运行并从最后一致的状态恢复。

**它能搜索网络吗？** 是的，在多次策略转向后仍然卡住时。搜索结果作为假设处理，机械验证后才应用。

**如何在 CI 中使用？** 使用 `Mode: exec` 或 `codex exec`。所有配置预先提供，输出为 JSON，退出码表示成功/失败。

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
