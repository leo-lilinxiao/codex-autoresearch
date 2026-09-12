# Codex Autoresearch

[English](../../README.md) | **中文**

面向 Codex 的自主、可度量实验循环。

告诉 Codex 你想达到的数值目标。它会先扫描仓库并向你确认，然后不断执行：修改一个点、验证、保留改进、回滚失败，直到达到目标。

适用于测试失败数、覆盖率、类型错误、告警数、延迟、产物体积、可复现的安全问题，以及任何可以被命令稳定测量的结果。

## 快速开始

在 Codex 中安装：

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

建议用 Full Access 打开一个干净的 Git 仓库：

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

然后调用：

```text
$codex-autoresearch 把 `python3 scripts/score.py` 的 error_count 降到 0
```

Codex 会在首次写入前确认：目标、可修改范围、当前值、目标值、指标命令、可选 guard，以及 foreground 或 background。

Codex 会沿用你已经给出的选择和授权。启动后会持续实验，不会逐轮要求确认；后台停止后，说“恢复”即可继续原配置，也可以补充新的方向。

## 工作方式

```text
读取证据 -> 修改一个明确的假设 -> 提交并测量
                                      |
                         改进且 guard 通过：保留
                         否则：git revert
                                      |
                              记录并继续
```

Codex 负责分析和改代码；控制脚本负责 Git 边界、测量、回滚和状态。

## 前台与后台

| | Foreground | Background |
|---|---|---|
| 运行位置 | 当前 Codex 任务 | 独立 controller |
| 持续运行 | Codex 官方 Goal | 每轮一个 `codex exec` worker |
| 适合 | 实时观察和指导 | 长时间或通宵运行 |
| 控制 | Goal 的暂停/恢复 | 用 `$codex-autoresearch` 查询、停止、恢复 |

Foreground 由 Codex 官方 Goal 持续运行。Background 不创建 Goal，由 controller 负责持续运行。安装不会修改 Codex 配置。

## 结果文件

所有文件位于未提交的 `autoresearch-results/`：

| 文件 | 用途 |
|---|---|
| `run.json` | 不可变的已确认配置 |
| `events.jsonl` | 仅追加的基线、实验和终止记录 |
| `logs/` | 完整的指标、guard 和 worker 输出 |
| `runtime.json` | 后台进程状态 |
| `runtime.log` | 后台 controller 事件 |

`events.jsonl` 是运行状态的唯一事实来源。缺失、损坏或矛盾的状态会直接报错，不会从旧文件或对话内容里猜测恢复。

## 查看运行结果

```text
$codex-autoresearch 查看实验历史
$codex-autoresearch 将实验历史导出为 TSV
$codex-autoresearch 生成 HTML 报告
```

历史表格和 HTML 都从验证后的事件动态生成。HTML 快照写入 `autoresearch-results/report.html`，不参与运行状态或恢复。

## 可靠性边界

- 新运行要求一个干净、具名的 Git 分支。
- 一次运行只管理一个仓库、一个主指标和一个目标值。
- 每个实验都会创建提交；失败实验使用 `git revert`。
- 超出范围的修改、分支或 HEAD 漂移、错误指标、命令失败、超时和回滚失败都会停止运行并给出日志路径。
- 只有保留指标达到已确认目标时，状态才会变为 `complete`。

## 要求

- 支持 Skills 和 Goals 的当前 Codex CLI
- Python 3.11+
- Git

安装方式见[安装文档](../INSTALL.md)，完整行为见[用户指南](../GUIDE.md)，常用场景见[示例](../EXAMPLES.md)。

MIT License。项目灵感来自 [Karpathy 的 autoresearch](https://github.com/karpathy/autoresearch)。
