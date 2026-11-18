# Codex Autoresearch

[English](../../README.md) | **中文**

给 Codex 用的实验助手：自动尝试改进，用数字验证结果。

告诉 Codex 你想把哪个数字推到多少。它会先看一遍仓库，跟你确认方案，然后围绕一个假设修改、测量，保留改进、回滚失败，持续实验直到达标。

只要能用命令稳定测出来的数字都可以：失败的测试数、覆盖率、类型错误、告警数、延迟、产物体积、可复现的安全问题，等等。

## 快速开始

在 Codex 里安装：

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

建议在一个干净的 Git 仓库里，用 Full Access 打开 Codex：

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

然后直接说：

```text
$codex-autoresearch 把 `python3 scripts/score.py` 的 error_count 降到 0
```

动手之前，Codex 会先跟你确认：目标、可以改哪些路径、当前值和目标值、用什么命令测、要不要 guard，以及在前台还是后台跑。

你已经说过的，它不会再问。确认之后就一直跑下去，不会每轮都来找你。后台停下以后，说一句“恢复”就按原来的配置继续，也可以顺便给个新方向。

## 工作方式

```text
读取证据 -> 修改一个明确的假设 -> 提交并测量
                                      |
                         改进且 guard 通过：保留
                         否则：git revert
                                      |
                              记录并继续
```

Codex 负责想办法、改代码。控制脚本负责记账：提交、测量、回滚，以及每次实验的记录。

## 前台与后台

| | Foreground | Background |
|---|---|---|
| 运行位置 | 当前 Codex 任务 | 独立的 controller |
| 靠什么持续 | Codex 的 Goal | 每轮启动一个新的 `codex exec` worker |
| 适合 | 边看边调方向 | 长时间或通宵跑 |
| 控制 | Goal 的暂停/恢复 | 用 `$codex-autoresearch` 查询、停止、恢复 |

两种模式规则一样，区别只在于谁让循环一直转下去：前台靠 Codex 的 Goal，后台靠一个独立的 controller。安装不会改动你的 Codex 配置。

## 结果文件

运行记录都放在 `autoresearch-results/` 里，不会被提交：

| 文件 | 用途 |
|---|---|
| `run.json` | 你确认过的配置，之后不再改动 |
| `events.jsonl` | 基线、每次实验和结束记录，只追加不修改 |
| `logs/` | 指标、guard 和 worker 的完整输出 |
| `runtime.json` | 后台进程状态 |
| `runtime.log` | 后台 controller 做过什么 |

`events.jsonl` 是唯一的事实来源。它缺了、坏了或者前后对不上，都会直接报错，不会拿旧文件或聊天记录去猜。

## 查看运行结果

```text
$codex-autoresearch 查看实验历史
$codex-autoresearch 将实验历史导出为 TSV
$codex-autoresearch 生成 HTML 报告
```

历史表格和 HTML 报告都是从事件记录现生成的。HTML 写在 `autoresearch-results/report.html`，只是一份快照，跟运行状态和恢复都没关系。

## 可靠性边界

- 开始新的运行，需要一个干净、有名字的 Git 分支。
- 一次运行只管一个仓库、一个指标、一个目标值。
- 每次实验都会提交。没变好或没过 guard 的实验，会用 `git revert` 回滚。
- 实验的指标命令非零退出或超时，会回滚并记为 `crash`，然后继续。连续 3 次崩溃才会停止运行。
- guard 超时按失败处理。首次建立基线时，指标测量和 guard 都必须成功。
- 超出 scope 的修改、分支或 HEAD 漂移、指标无效、进程清理失败和回滚失败，都会停止运行并给出诊断信息。
- 运行期间别动这个工作目录：在 scope 内改的东西会被并进当前实验一起提交。想同时继续开发，另开一个 `git worktree`。
- 只有保留下来的结果真的达到目标，状态才会变成 `complete`。

## 要求

- 支持 Skills 和 Goals 的当前 Codex CLI
- Python 3.11+
- Git

怎么安装看[安装文档](../INSTALL.md)，详细用法看[用户指南](../GUIDE.md)，常见场景看[示例](../EXAMPLES.md)。

MIT License。项目灵感来自 [Karpathy 的 autoresearch](https://github.com/karpathy/autoresearch)。
