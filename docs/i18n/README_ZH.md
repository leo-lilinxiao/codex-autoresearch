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

---

核心思路：告诉 Codex 你想改善什么，然后走开。它会修改代码、验证结果、保留或丢弃，然后重复。你回来时会看到一份实验日志和一个更好的代码库。

灵感来自 [Karpathy 的 autoresearch](https://github.com/karpathy/autoresearch)，从 ML 推广到一切可以机械验证的目标：测试覆盖率、类型错误、延迟、lint 警告、安全漏洞、发布就绪检查 — 只要一条命令能判断是否改善了，循环就能迭代。

## 快速上手

```text
# 在 Codex 中安装（推荐）
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

重启 Codex，然后在项目中打开：

```
你:    $codex-autoresearch
       把 TypeScript 代码里所有的 any 类型都消除掉

Codex: 在 src/**/*.ts 中找到 47 个 `any`。
       Results 目录：./autoresearch-results/
       指标：any 出现次数（当前 47），方向：降低
       验证：grep 计数 + tsc --noEmit 守护
       运行模式：foreground 还是 background？

你:    Background，go。跑一晚上。

Codex: 开始后台运行 -- 基线：47。持续迭代中。
```

改善累积，失败回滚，全程记录。

手动复制、symlink、用户级安装方式见 [INSTALL.md](../INSTALL.md)。完整操作手册见 [GUIDE.md](../GUIDE.md)。

## 工作原理

```
你说一句话  →  Codex 扫描并确认  →  你说 "go"
                                       |
                          +------------+------------+
                          |                         |
                     foreground                background
                    (当前会话)               (后台，可以过夜)
                          |                         |
                          +------------+------------+
                                       |
                                       v
                             +-------------------+
                             |     核心循环       |
                             |                   |
                             |  改一个地方       |
                             |  git commit       |
                             |  跑验证           |
                             |  改善了？保留     |
                             |  变差了？回滚     |
                             |  记录结果         |
                             |  重复             |
                             +-------------------+
```

就这么简单。你二选一：foreground 在当前会话里跑，background 交给后台进程让你去睡觉。同一个循环，但不能同时跑。

## 你说什么 vs 发生什么

| 你说的话 | 发生了什么 |
|---------|-----------|
| "提升我的测试覆盖率" | 持续迭代直到目标达成或被中断 |
| "修复那 12 个失败的测试" | 逐个修复直到全部通过 |
| "为什么 API 返回 503？" | 用可证伪的假设追踪根因 |
| "这段代码安全吗？" | STRIDE + OWASP 审计，每个发现都有代码证据 |
| "准备发布" | 验证就绪状态，生成检查清单，门控发布 |
| "我想优化但不知道该测量什么" | 分析仓库，建议指标，生成配置 |

在幕后，Codex 将你的话映射到 7 个模式之一（loop、plan、debug、fix、security、ship、exec）。你不需要选择模式。

## Codex 自动推断的内容

你不需要写配置。Codex 从你的话和仓库中推断一切：

| 它需要什么 | 如何获取 | 示例 |
|-----------|---------|------|
| 目标 | 你说的话 | "消除所有 any 类型" |
| 范围 | 扫描仓库结构 | `src/**/*.ts` |
| 指标 | 基于目标 + 工具链提出 | any 计数（当前：47） |
| 方向 | 从 "改善" / "减少" / "消除" 推断 | 降低 |
| 验证命令 | 匹配仓库工具链 | `grep` 计数 + `tsc --noEmit` |
| 守护 | 如果存在回归风险则建议 | `npm test` |

开始之前，Codex 总是展示它发现的内容并请求确认。然后你选 foreground 或 background，说 "go"。
默认情况下，Results 目录应留在当前启动上下文里：如果你是在 git 仓库内启动 Codex，该仓库根目录就是默认的 workspace root；如果你是在 git 仓库外启动 Codex，当前启动目录就是默认的 workspace root。除非你明确确认要使用更大的多仓库 workspace，否则 Codex 不应该静默把它上推到父目录。启动前的确认摘要也应始终展示最终选择的 Results 目录。

## 卡住时怎么办

循环不会盲目重试，而是逐级升级：

| 触发条件 | 动作 |
|---------|------|
| 连续 3 次失败 | **REFINE** -- 在当前策略内调整 |
| 连续 5 次失败 | **PIVOT** -- 尝试根本不同的方法 |
| 2 次 PIVOT 无进展 | **Web 搜索** -- 寻找外部解决方案 |
| 3 次 PIVOT 无进展 | **停止** -- 报告需要人工介入 |

一次成功即重置所有计数器。

## 结果日志

每次迭代记录在 `autoresearch-results/results.tsv` 中：

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module
2          -        49      +8      discard   generic wrapper introduced new anys
3          d4e5f6g  38      -3      keep      type-narrow API response handlers
```

失败的实验从 git 回滚，但保留在日志中。日志才是真正的审计记录，而 `autoresearch-results/state.json` 是恢复快照。

## 更多功能

以下内容在 [GUIDE.md](../GUIDE.md) 中详细介绍：

- **跨运行学习** -- 过去运行的经验会影响未来的假设生成
- **并行实验** -- 通过 git worktree 同时测试最多 3 个假设
- **会话恢复** -- 中断的运行从最后一致状态继续
- **CI/CD 模式** (`exec`) -- 非交互，JSON 输出，用于自动化流水线
- **双门验证** -- 分开的 verify（改善了吗？）和 guard（其他东西没坏吧？）
- **会话 hooks** -- 自动安装；跨会话边界保持 Codex 的运行状态

## FAQ

**每次改动都很小，能不能尝试更大的改进？**
默认情况下循环倾向于小步可验证的改动 — 这是设计如此。但它可以做更大的事：在 prompt 里描述一个更大的假设（比如"尝试把 attention 机制换成 linear attention，跑完整 eval"），它会把这当作一个完整实验来验证。最佳用法是人来定研究方向，模型来做高强度执行和分析。

**这个更适合工程优化还是科研？**
当目标和指标明确时它最强 — 提升覆盖率、减少错误、降低延迟。如果研究方向本身还不确定，先用 `plan` 模式探索，确定要测量什么之后再切到 `loop`。把它理解为人机协作：你提供判断，它提供迭代速度。

**怎么停止？** Foreground：中断 Codex。Background：`$codex-autoresearch` 然后要求停止。

**中断后能恢复吗？** 能。自动从 `autoresearch-results/state.json` 恢复。

**如何在 CI 中使用？** `Mode: exec` 配合 `codex exec`。所有配置预先提供，JSON 输出，退出码 0/1/2。

## 文档

| 文档 | 内容 |
|-----|------|
| [INSTALL.md](../INSTALL.md) | 所有安装方式、skill 发现路径、hooks 设置 |
| [GUIDE.md](../GUIDE.md) | 完整操作手册：模式、配置字段、安全模型、高级用法 |
| [EXAMPLES.md](../EXAMPLES.md) | 按领域分类的配方：覆盖率、性能、类型、安全等 |

## 致谢

基于 [Karpathy 的 autoresearch](https://github.com/karpathy/autoresearch) 的理念构建。Codex skills 平台由 [OpenAI](https://openai.com) 提供。

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

## 许可证

MIT -- 见 [LICENSE](../../LICENSE)。
