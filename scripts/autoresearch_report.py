#!/usr/bin/env python3
"""Read-only terminal, TSV, and HTML views for validated autoresearch events."""

from __future__ import annotations

import csv
import html
import io
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

from autoresearch_core import RunState, decimal_json, parse_decimal, utc_now


@dataclass(frozen=True)
class HistoryRow:
    seq: int
    iteration: int
    event: str
    previous_metric: str
    trial_metric: str
    retained_metric: str
    description: str
    trial_commit: str
    revert_commit: str
    head: str
    verify_log: str
    guard: str
    guard_log: str
    time: str


def _single_line(value: Any) -> str:
    if value is None:
        return ""
    cleaned: list[str] = []
    for character in str(value):
        codepoint = ord(character)
        if character in "\r\n\t":
            cleaned.append(" ")
        elif codepoint < 32 or codepoint == 127:
            continue
        else:
            cleaned.append(character)
    return " ".join("".join(cleaned).split())


def _metric(value: Any) -> str:
    if value is None or value == "":
        return ""
    parsed = parse_decimal(value, field="report metric")
    return str(decimal_json(parsed))


def history_rows(events: list[dict[str, Any]]) -> list[HistoryRow]:
    rows: list[HistoryRow] = []
    iteration = 0
    for event in events:
        event_type = event["event"]
        if event_type == "baseline":
            rows.append(
                HistoryRow(
                    seq=event["seq"],
                    iteration=0,
                    event="baseline",
                    previous_metric="",
                    trial_metric="",
                    retained_metric=_metric(event["metric"]),
                    description="Initial measurement",
                    trial_commit="",
                    revert_commit="",
                    head=_single_line(event["head"]),
                    verify_log=_single_line(event["verify_log"]),
                    guard="",
                    guard_log=_single_line(event["guard_log"]),
                    time=_single_line(event["time"]),
                )
            )
            continue
        if event_type == "iteration":
            iteration = event["iteration"]
            rows.append(
                HistoryRow(
                    seq=event["seq"],
                    iteration=iteration,
                    event=event["outcome"],
                    previous_metric=_metric(event["previous_metric"]),
                    trial_metric=_metric(event["trial_metric"]),
                    retained_metric=_metric(event["retained_metric"]),
                    description=_single_line(event["description"]),
                    trial_commit=_single_line(event["trial_commit"]),
                    revert_commit=_single_line(event["revert_commit"]),
                    head=_single_line(event["head"]),
                    verify_log=_single_line(event["verify_log"]),
                    guard=_single_line(event["guard"]),
                    guard_log=_single_line(event["guard_log"]),
                    time=_single_line(event["time"]),
                )
            )
            continue
        description = event.get("reason", event.get("note", ""))
        rows.append(
            HistoryRow(
                seq=event["seq"],
                iteration=iteration,
                event=event_type,
                previous_metric="",
                trial_metric="",
                retained_metric=_metric(event.get("metric")),
                description=_single_line(description),
                trial_commit=_single_line(event.get("trial_commit")),
                revert_commit=_single_line(event.get("revert_commit")),
                head=_single_line(event.get("head")),
                verify_log=_single_line(event.get("log")),
                guard="",
                guard_log="",
                time=_single_line(event["time"]),
            )
        )
    return rows


def _shorten(value: str, limit: int) -> str:
    if _display_width(value) <= limit:
        return value
    output: list[str] = []
    width = 0
    for character in value:
        character_width = _display_width(character)
        if width + character_width > limit - 3:
            break
        output.append(character)
        width += character_width
    return "".join(output).rstrip() + "..."


def _display_width(value: str) -> int:
    width = 0
    for character in value:
        if unicodedata.combining(character):
            continue
        width += 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
    return width


def _pad(value: str, width: int, *, right: bool) -> str:
    padding = " " * max(0, width - _display_width(value))
    return padding + value if right else value + padding


def render_history_table(
    run: dict[str, Any], state: RunState, events: list[dict[str, Any]]
) -> str:
    rows = history_rows(events)
    headers = ("SEQ", "ITER", "EVENT", "PREVIOUS", "TRIAL", "RETAINED", "DESCRIPTION")
    cells = [
        (
            str(row.seq),
            str(row.iteration),
            row.event,
            row.previous_metric or "-",
            row.trial_metric or "-",
            row.retained_metric or "-",
            _shorten(row.description, 72) or "-",
        )
        for row in rows
    ]
    widths = [
        max(_display_width(headers[index]), *(_display_width(row[index]) for row in cells))
        for index in range(len(headers))
    ]

    def format_row(row: tuple[str, ...]) -> str:
        output = []
        for index, value in enumerate(row):
            if index in {0, 1, 3, 4, 5}:
                output.append(_pad(value, widths[index], right=True))
            else:
                output.append(_pad(value, widths[index], right=False))
        return "  ".join(output).rstrip()

    baseline = _metric(events[0]["metric"])
    summary = [
        "Codex Autoresearch",
        f"Run: {run['run_id'][:8]}  Status: {state.status}  Mode: {run['mode']}",
        (
            f"Metric: {run['metric']['name']}  {baseline} -> {_metric(state.metric)}  "
            f"Target: {_metric(run['target'])} ({run['metric']['direction']} is better)"
        ),
        "",
        format_row(headers),
        "  ".join("-" * width for width in widths),
    ]
    summary.extend(format_row(row) for row in cells)
    return "\n".join(summary) + "\n"


TSV_FIELDS = (
    "seq",
    "iteration",
    "event",
    "previous_metric",
    "trial_metric",
    "retained_metric",
    "description",
    "trial_commit",
    "revert_commit",
    "head",
    "verify_log",
    "guard",
    "guard_log",
    "time",
)


def _spreadsheet_text(value: str) -> str:
    if value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def render_history_tsv(events: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, dialect="excel-tab", lineterminator="\n")
    writer.writerow(TSV_FIELDS)
    for row in history_rows(events):
        values = []
        for field in TSV_FIELDS:
            value = str(getattr(row, field))
            if field not in {
                "seq",
                "iteration",
                "previous_metric",
                "trial_metric",
                "retained_metric",
            }:
                value = _spreadsheet_text(value)
            values.append(value)
        writer.writerow(values)
    return output.getvalue()


def _escape(value: Any) -> str:
    return html.escape(_single_line(value), quote=True)


def _short_hash(value: str) -> str:
    return value[:8] if value else ""


def _safe_log_link(path: str, label: str) -> str:
    if not path:
        return '<span class="muted">-</span>'
    normalized = path.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    safe = not candidate.is_absolute() and ".." not in candidate.parts and candidate.parts[:1] == ("logs",)
    escaped_path = _escape(path)
    if not safe:
        return f"<code>{escaped_path}</code>"
    href = quote(normalized, safe="/-_.")
    return f'<a href="{href}">{_escape(label)}</a>'


def _metric_chart(run: dict[str, Any], events: list[dict[str, Any]]) -> str:
    baseline = parse_decimal(events[0]["metric"], field="baseline metric")
    retained: list[tuple[int, Decimal]] = [(0, baseline)]
    trials: list[tuple[int, Decimal, str]] = []
    for event in events:
        if event["event"] != "iteration":
            continue
        index = event["iteration"]
        retained.append(
            (index, parse_decimal(event["retained_metric"], field="retained metric"))
        )
        if event["trial_metric"] is not None:
            trials.append(
                (index, parse_decimal(event["trial_metric"], field="trial metric"), event["outcome"])
            )

    target = parse_decimal(run["target"], field="target")
    values = [value for _, value in retained] + [value for _, value, _ in trials] + [target]
    minimum = min(values)
    maximum = max(values)
    if minimum == maximum:
        minimum -= Decimal(1)
        maximum += Decimal(1)
    else:
        padding = (maximum - minimum) * Decimal("0.08")
        minimum -= padding
        maximum += padding

    view_width = Decimal(960)
    view_height = Decimal(280)
    left = Decimal(72)
    right = Decimal(24)
    top = Decimal(28)
    bottom = Decimal(56)
    plot_width = view_width - left - right
    plot_height = view_height - top - bottom
    max_iteration = max((index for index, _ in retained), default=0)

    def x_position(index: int) -> Decimal:
        if max_iteration == 0:
            return left
        return left + plot_width * Decimal(index) / Decimal(max_iteration)

    def y_position(value: Decimal) -> Decimal:
        return top + (maximum - value) * plot_height / (maximum - minimum)

    def coordinate(value: Decimal) -> str:
        return f"{float(value):.2f}"

    grid = []
    for fraction in (Decimal(0), Decimal("0.25"), Decimal("0.5"), Decimal("0.75"), Decimal(1)):
        y = top + plot_height * fraction
        grid.append(
            f'<line class="grid-line" x1="{coordinate(left)}" y1="{coordinate(y)}" '
            f'x2="{coordinate(left + plot_width)}" y2="{coordinate(y)}" />'
        )

    retained_points = " ".join(
        f"{coordinate(x_position(index))},{coordinate(y_position(value))}"
        for index, value in retained
    )
    retained_circles = "".join(
        f'<circle class="retained-point" cx="{coordinate(x_position(index))}" '
        f'cy="{coordinate(y_position(value))}" r="4"><title>Iteration {index}: '
        f'{_escape(_metric(value))} retained</title></circle>'
        for index, value in retained
    )
    trial_circles = "".join(
        f'<circle class="trial-point {outcome}" cx="{coordinate(x_position(index))}" '
        f'cy="{coordinate(y_position(value))}" r="6"><title>Iteration {index}: '
        f'{_escape(_metric(value))} ({_escape(outcome)})</title></circle>'
        for index, value, outcome in trials
    )
    target_y = coordinate(y_position(target))
    last_x = coordinate(x_position(max_iteration))
    max_label = _escape(_metric(max(values)))
    min_label = _escape(_metric(min(values)))
    target_label = _escape(_metric(target))
    return f"""
<svg class="metric-chart" viewBox="0 0 960 280" role="img" aria-label="Retained and trial metric trajectory">
  {''.join(grid)}
  <line class="axis-line" x1="{coordinate(left)}" y1="{coordinate(top + plot_height)}" x2="{coordinate(left + plot_width)}" y2="{coordinate(top + plot_height)}" />
  <line class="target-line" x1="{coordinate(left)}" y1="{target_y}" x2="{coordinate(left + plot_width)}" y2="{target_y}" />
  <polyline class="retained-line" points="{retained_points}" />
  {trial_circles}
  {retained_circles}
  <text class="axis-label" x="{coordinate(left - Decimal(12))}" y="{coordinate(y_position(max(values)) + Decimal(4))}" text-anchor="end">{max_label}</text>
  <text class="axis-label" x="{coordinate(left - Decimal(12))}" y="{coordinate(y_position(min(values)) + Decimal(4))}" text-anchor="end">{min_label}</text>
  <text class="target-label" x="{coordinate(left + Decimal(8))}" y="{coordinate(y_position(target) - Decimal(8))}">Target {target_label}</text>
  <text class="axis-label" x="{coordinate(left)}" y="{coordinate(top + plot_height + Decimal(26))}">0</text>
  <text class="axis-label" x="{last_x}" y="{coordinate(top + plot_height + Decimal(26))}" text-anchor="end">{max_iteration}</text>
  <g class="legend" transform="translate(650 252)">
    <line class="retained-line" x1="0" y1="0" x2="24" y2="0" /><text x="32" y="4">Retained</text>
    <circle class="trial-point keep" cx="122" cy="0" r="5" /><text x="134" y="4">Keep</text>
    <circle class="trial-point discard" cx="200" cy="0" r="5" /><text x="212" y="4">Discard</text>
  </g>
</svg>""".strip()


def render_html_report(
    run: dict[str, Any], state: RunState, events: list[dict[str, Any]]
) -> str:
    rows = history_rows(events)
    baseline = _metric(events[0]["metric"])
    generated_at = utc_now()
    status_class = (
        state.status
        if state.status in {"active", "complete", "blocked", "error", "stopped"}
        else "active"
    )
    known_events = {
        "baseline",
        "keep",
        "discard",
        "crash",
        "complete",
        "blocked",
        "error",
        "stopped",
        "resumed",
    }
    table_rows: list[str] = []
    for row in rows:
        event_class = row.event if row.event in known_events else "baseline"
        commits = []
        if row.trial_commit:
            commits.append(
                f'<code title="{_escape(row.trial_commit)}">'
                f"{_escape(_short_hash(row.trial_commit))}</code>"
            )
        if row.revert_commit:
            commits.append(
                '<span class="commit-separator">revert</span> '
                f'<code title="{_escape(row.revert_commit)}">'
                f"{_escape(_short_hash(row.revert_commit))}</code>"
            )
        logs = [_safe_log_link(row.verify_log, "verify")]
        if row.guard_log:
            logs.append(_safe_log_link(row.guard_log, "guard"))
        table_rows.append(
            f"""
            <tr>
              <td class="numeric">{row.iteration}</td>
              <td><span class="event-label {event_class}">{_escape(row.event)}</span></td>
              <td class="numeric">{_escape(row.previous_metric or '-')}</td>
              <td class="numeric">{_escape(row.trial_metric or '-')}</td>
              <td class="numeric retained">{_escape(row.retained_metric or '-')}</td>
              <td class="description">{_escape(row.description or '-')}</td>
              <td>{' '.join(commits) if commits else '<span class="muted">-</span>'}</td>
              <td>{' / '.join(logs)}</td>
              <td class="time">{_escape(row.time)}</td>
            </tr>"""
        )

    guard = run["guard"] or "None"
    iteration_limit = run["max_iterations"] if run["max_iterations"] is not None else "Unlimited"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
  <link rel="icon" href="data:,">
  <title>Codex Autoresearch Report - {_escape(run['goal'])}</title>
  <style>
    :root {{ color-scheme: light; --ink: #172033; --muted: #647084; --line: #d7dde7; --panel: #f6f8fb; --blue: #2563eb; --green: #15803d; --red: #b42318; --amber: #a15c00; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #ffffff; color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 14px; line-height: 1.5; letter-spacing: 0; }}
    header {{ border-bottom: 1px solid var(--line); background: #f9fafc; }}
    .wrap {{ width: min(1180px, calc(100% - 40px)); margin: 0 auto; }}
    .header-inner {{ padding: 34px 0 30px; }}
    .product {{ margin: 0 0 8px; color: var(--blue); font-size: 13px; font-weight: 700; }}
    h1 {{ max-width: 900px; margin: 0; font-size: 30px; line-height: 1.2; font-weight: 720; overflow-wrap: anywhere; }}
    .header-meta {{ display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; margin-top: 18px; color: var(--muted); }}
    .status {{ display: inline-flex; align-items: center; min-height: 28px; padding: 3px 9px; border: 1px solid currentColor; border-radius: 4px; font-weight: 700; }}
    .status.complete {{ color: var(--green); background: #f0fdf4; }} .status.error {{ color: var(--red); background: #fef3f2; }}
    .status.blocked, .status.stopped {{ color: var(--amber); background: #fff8e7; }} .status.active {{ color: var(--blue); background: #eff6ff; }}
    main {{ padding: 28px 0 44px; }}
    section {{ margin-top: 34px; }} section:first-child {{ margin-top: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; line-height: 1.3; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 0; }}
    .summary-grid > div {{ min-width: 0; padding: 15px 16px; border: 1px solid var(--line); border-radius: 6px; background: #fff; }}
    dt {{ color: var(--muted); font-size: 12px; }} dd {{ margin: 5px 0 0; font-size: 19px; font-weight: 700; overflow-wrap: anywhere; }}
    .chart-shell {{ border: 1px solid var(--line); border-radius: 6px; padding: 12px 14px 4px; overflow: hidden; background: #fff; }}
    .metric-chart {{ display: block; width: 100%; height: auto; aspect-ratio: 24 / 7; }}
    .grid-line {{ stroke: #e7ebf1; stroke-width: 1; }} .axis-line {{ stroke: #8993a4; stroke-width: 1; }}
    .target-line {{ stroke: #a15c00; stroke-width: 1.5; stroke-dasharray: 6 5; }} .target-label {{ fill: #815000; font-size: 12px; }}
    .retained-line {{ fill: none; stroke: var(--blue); stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }}
    .retained-point {{ fill: #fff; stroke: var(--blue); stroke-width: 3; }} .trial-point {{ stroke-width: 2; }}
    .trial-point.keep {{ fill: #dcfce7; stroke: var(--green); }} .trial-point.discard {{ fill: #fee4e2; stroke: var(--red); }}
    .axis-label, .legend text {{ fill: var(--muted); font-size: 12px; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; }}
    table {{ width: 100%; min-width: 1060px; border-collapse: collapse; background: #fff; }}
    th {{ padding: 10px 12px; border-bottom: 1px solid var(--line); background: var(--panel); color: #485468; font-size: 12px; text-align: left; font-weight: 700; }}
    td {{ padding: 11px 12px; border-bottom: 1px solid #e8ecf2; vertical-align: top; }} tr:last-child td {{ border-bottom: 0; }}
    tbody tr:hover {{ background: #fafcff; }} .numeric {{ text-align: right; font-variant-numeric: tabular-nums; }} .retained {{ font-weight: 700; }}
    .description {{ min-width: 240px; max-width: 420px; overflow-wrap: anywhere; }} .time {{ white-space: nowrap; color: var(--muted); font-size: 12px; }}
    .event-label {{ display: inline-block; min-width: 66px; padding: 2px 6px; border-radius: 4px; background: #edf1f6; color: #465268; font-size: 12px; font-weight: 700; text-align: center; }}
    .event-label.keep, .event-label.complete {{ color: var(--green); background: #e9f8ee; }} .event-label.discard, .event-label.crash, .event-label.error {{ color: var(--red); background: #fdf0ef; }}
    .event-label.blocked, .event-label.stopped {{ color: var(--amber); background: #fff4d8; }} .event-label.resumed {{ color: var(--blue); background: #eaf2ff; }}
    code {{ font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-size: 12px; overflow-wrap: anywhere; }}
    a {{ color: #175cd3; text-decoration-thickness: 1px; text-underline-offset: 2px; }} .muted {{ color: #8a94a5; }} .commit-separator {{ margin-left: 5px; color: var(--muted); font-size: 11px; }}
    .config {{ display: grid; grid-template-columns: 160px minmax(0, 1fr); margin: 0; border-top: 1px solid var(--line); }}
    .config dt, .config dd {{ margin: 0; padding: 10px 0; border-bottom: 1px solid var(--line); font-size: 13px; }} .config dd {{ font-weight: 500; overflow-wrap: anywhere; }}
    footer {{ margin-top: 40px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; }}
    @media (max-width: 760px) {{ .wrap {{ width: min(100% - 24px, 1180px); }} .header-inner {{ padding: 24px 0; }} h1 {{ font-size: 24px; }} .summary-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .config {{ grid-template-columns: 1fr; }} .config dt {{ padding-bottom: 2px; border-bottom: 0; }} .config dd {{ padding-top: 0; }} }}
  </style>
</head>
<body>
  <header>
    <div class="wrap header-inner">
      <p class="product">CODEX AUTORESEARCH</p>
      <h1>{_escape(run['goal'])}</h1>
      <div class="header-meta">
        <span class="status {status_class}">{_escape(state.status)}</span>
        <span>Run <code>{_escape(run['run_id'][:12])}</code></span>
        <span>{_escape(run['mode'])}</span>
        <span>{_escape(run['branch'])}</span>
      </div>
    </div>
  </header>
  <main class="wrap">
    <section aria-labelledby="summary-heading">
      <h2 id="summary-heading">Run summary</h2>
      <dl class="summary-grid">
        <div><dt>Baseline</dt><dd>{_escape(baseline)}</dd></div>
        <div><dt>Current</dt><dd>{_escape(_metric(state.metric))}</dd></div>
        <div><dt>Target</dt><dd>{_escape(_metric(run['target']))}</dd></div>
        <div><dt>Iterations</dt><dd>{state.iterations}</dd></div>
      </dl>
    </section>
    <section aria-labelledby="trajectory-heading">
      <h2 id="trajectory-heading">Metric trajectory</h2>
      <div class="chart-shell">{_metric_chart(run, events)}</div>
    </section>
    <section aria-labelledby="history-heading">
      <h2 id="history-heading">Experiment history</h2>
      <div class="table-wrap" role="region" aria-label="Experiment history table" tabindex="0">
        <table>
          <thead><tr><th>Iter</th><th>Event</th><th>Previous</th><th>Trial</th><th>Retained</th><th>Description</th><th>Commits</th><th>Logs</th><th>Time</th></tr></thead>
          <tbody>{''.join(table_rows)}</tbody>
        </table>
      </div>
    </section>
    <section aria-labelledby="config-heading">
      <h2 id="config-heading">Configuration</h2>
      <dl class="config">
        <dt>Metric</dt><dd>{_escape(run['metric']['name'])} ({_escape(run['metric']['direction'])} is better)</dd>
        <dt>Scope</dt><dd><code>{_escape(', '.join(run['scope']))}</code></dd>
        <dt>Verify</dt><dd><code>{_escape(run['metric']['command'])}</code></dd>
        <dt>Guard</dt><dd><code>{_escape(guard)}</code></dd>
        <dt>Iteration limit</dt><dd>{_escape(iteration_limit)}</dd>
      </dl>
    </section>
    <footer>Generated {_escape(generated_at)} from validated <code>run.json</code> and <code>events.jsonl</code>.</footer>
  </main>
</body>
</html>
"""
