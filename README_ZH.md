<div align="center">

# Codex Autoresearch

[Codex](https://openai.com/codex) 的自主迭代协议。定义目标、指标和验证命令 -- Codex 处理剩下的一切。

[![Codex Skill](https://img.shields.io/badge/Codex-Skill-blue?logo=openai&logoColor=white)](https://developers.openai.com/codex/skills)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[架构](#架构) . [30秒上手](#30秒上手) . [模式](#模式) . [配置](#配置) . [操作手册](GUIDE.md) . [配方集](EXAMPLES.md)

</div>

---

## 它做什么

一个 Codex skill，在你的代码库上运行 "修改-验证-决策" 循环。每次迭代做一个原子改动，用机械化指标验证，然后保留或丢弃。进展累积在 git 中；失败自动回滚。适用于任何语言、任何框架、任何可测量的目标。

灵感来自 [Karpathy 的 autoresearch](https://github.com/karpathy/autoresearch) 原则，推广到 ML 之外的所有领域。

### 为什么做这个

Karpathy 的 autoresearch 证明了一个简单的循环 -- 修改、验证、保留或丢弃、重复 -- 就能在一夜之间把 ML 训练从基线推进到新高。codex-autoresearch 把这个循环泛化到软件工程中一切有数字的场景。测试覆盖率、类型错误、性能延迟、lint 警告 -- 只要有指标，就能自主迭代。

---

## 架构

```
                    +------------------+
                    |     读取上下文     |
                    +--------+---------+
                             |
                    +--------v---------+
                    |    建立基线        |  <-- 迭代 #0
                    +--------+---------+
                             |
              +--------------v--------------+
              |                             |
              |    +-------------------+    |
              |    |   选择假设         |    |
              |    +--------+----------+    |
              |             |               |
              |    +--------v----------+    |
              |    |   做一个改动       |    |
              |    +--------+----------+    |
              |             |               |
              |    +--------v----------+    |
              |    |   git commit      |    |
              |    +--------+----------+    |
              |             |               |
              |    +--------v----------+    |
              |    |   运行验证         |    |
              |    +--------+----------+    |
              |             |               |
              |          改善了?             |
              |        /         \          |
              |       是          否         |
              |      /              \        |
              | +---v----+    +-----v----+  |
              | |  保留   |    |  回滚    |  |
              | +---+----+    +-----+----+  |
              |      \            /          |
              |    +--v----------v--+       |
              |    |    记录结果     |       |
              |    +-------+--------+       |
              |            |                |
              +------------+ (重复)         |
              |                             |
              +-----------------------------+
```

循环持续运行直到中断（无界）或恰好 N 次迭代（通过 `Iterations: N` 设定上限）。

**伪代码：**

```
LOOP (forever or N times):
  1. Review current state + git history + results log
  2. Pick ONE hypothesis (based on what worked, what failed, what's untried)
  3. Make ONE atomic change
  4. git commit (before verification)
  5. Run mechanical verification
  6. Improved -> keep. Worse -> git reset. Crashed -> fix or skip.
  7. Log the result
  8. Repeat. Never stop. Never ask.
```

---

## 30秒上手

**1. 安装：**

克隆并复制到项目中：
```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

或在 Codex 中使用 skill installer：
```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

**2. 在项目中打开 Codex 并运行：**

用一句话告诉 Codex 你想做什么：

```text
$codex-autoresearch
把 TypeScript 代码里所有的 any 类型都消除掉
```

Codex 扫描仓库后，**一定会先确认**再开始 -- 即使目标看起来很明确：

```
Codex: 在 src/**/*.ts 中找到 47 个 `any`。

       已确认：
       - 目标：消除 src/**/*.ts 中所有 any 类型
       - 指标：any 出现次数（当前 47），方向：降低
       - 验证：grep 计数 + tsc --noEmit 守护

       还需确认：
       - 跑到全部消除，还是限制在 N 次迭代？
       - 除了 tsc 还有其他安全检查吗？

       下一步：回复 "go" 开始，或告诉我要改什么。

你:    go，跑一晚上。

Codex: 开始 -- 基线：47。持续迭代直到你中断。
```

改善累积，失败回滚，全程记录。

高级用户也可以直接用结构化 key-value 配置 -- 见 [GUIDE.md](GUIDE.md)。

更多安装方式见 [INSTALL.md](INSTALL.md)。

---

## 模式

六种模式，统一调用方式：`$codex-autoresearch` 后跟一句自然语言。Codex 自动检测模式并通过对话引导补全配置。

| 模式 | 适用场景 | 何时停止 |
|------|----------|----------|
| `loop` | 有可测量的优化目标 | 中断或 N 次迭代 |
| `plan` | 有目标但不确定配置 | 生成配置块 |
| `debug` | 需要带证据的根因分析 | 所有假设已测试或 N 次迭代 |
| `fix` | 有东西坏了需要修复 | 错误数归零 |
| `security` | 需要结构化漏洞审计 | 所有攻击面已覆盖或 N 次迭代 |
| `ship` | 需要有门控的发布验证 | 所有检查项通过 |

**快速选择：**

```
"我要优化 X"              -->  loop（指标不确定就用 plan）
"有东西坏了"              -->  fix（原因不明就用 debug）
"这段代码安全吗？"        -->  security
"准备发布"                -->  ship
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
| 有信心地发布 | `ship` | `--auto` 或 `--dry-run` |

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

8 阶段门控发布。自动检测发布类型。

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

各模式的标志和高级选项见 [GUIDE.md](GUIDE.md)。

---

## 模式组合

模式可以顺序组合：

```
plan  -->  loop              # 先生成配置，再执行
debug -->  fix --from-debug  # 先找 bug，再修复
security --fix               # 审计并修复一步到位
```

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

| 关注点 | 处理方式 |
|--------|----------|
| 脏工作区 | 循环拒绝启动；建议用 `plan` 模式或干净分支 |
| 失败的改动 | `git reset --hard HEAD~1` 保持历史干净；结果日志是真正的审计记录 |
| Guard 失败 | 最多 2 次重新调整，然后回滚 |
| 语法错误 | 立即修复，不计为迭代 |
| 运行时崩溃 | 最多 3 次修复尝试，然后跳过 |
| 资源耗尽 | 回滚，尝试更小的变体 |
| 进程挂起 | 超时后终止，回滚 |
| 卡住（连续 5+ 次丢弃） | 重读所有上下文，审视规律，尝试更大胆的改动 |
| 循环中遇到不确定 | 自主采用最佳实践，绝不中断问用户 |
| 外部副作用 | `ship` 模式需显式确认 |

---

## 项目结构

```
codex-autoresearch/
  SKILL.md                          # skill 入口（Codex 加载）
  README.md                         # 英文文档
  README_ZH.md                      # 本文件
  INSTALL.md                        # 安装指南
  GUIDE.md                          # 操作手册
  EXAMPLES.md                       # 按领域分类的配方集
  CONTRIBUTING.md                   # 贡献指南
  LICENSE                           # MIT
  agents/
    openai.yaml                     # Codex UI 元数据
  scripts/
    validate_skill_structure.sh     # 结构验证脚本
  references/
    autonomous-loop-protocol.md     # 循环协议规范
    core-principles.md              # 通用原则
    plan-workflow.md                # plan 模式规范
    debug-workflow.md               # debug 模式规范
    fix-workflow.md                 # fix 模式规范
    security-workflow.md            # security 模式规范
    ship-workflow.md                # ship 模式规范
    interaction-wizard.md           # 交互式设置契约
    structured-output-spec.md       # 输出格式规范
    modes.md                        # 模式索引
    results-logging.md              # TSV 格式规范
```

---

## FAQ

**如何选指标？** 用 `Mode: plan`，它会分析代码库并建议。

**支持什么语言？** 全部。协议与语言无关，只有验证命令是领域特定的。

**怎么停止？** 中断 Codex，或设置 `Iterations: N`。git 状态始终一致，因为提交在验证之前。

**security 模式会改代码吗？** 不会。只读分析。用 `--fix` 选择性修复。

**迭代多少次？** 取决于任务。定向修复 5 次，探索性 10-20 次，过夜运行不设限。

---

## 致谢

本项目基于 [Karpathy 的 autoresearch](https://github.com/karpathy/autoresearch) 的理念构建。Codex skills 平台由 [OpenAI](https://openai.com) 提供。

---

## 许可证

MIT -- 见 [LICENSE](LICENSE)。
