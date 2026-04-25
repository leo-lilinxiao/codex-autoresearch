#!/usr/bin/env python3
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from autoresearch_core import AutoresearchError, decimal_to_json_number, improvement, parse_decimal

VALID_OPERATORS = {"<", "<=", ">", ">=", "=="}


def parse_criteria(criteria: Any, *, field_name: str) -> list[dict[str, Any]]:
    if criteria in (None, "", []):
        return []
    if not isinstance(criteria, list):
        raise AutoresearchError(f"{field_name} must be a list of criterion objects.")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(criteria):
        if not isinstance(item, dict):
            raise AutoresearchError(f"{field_name}[{index}] must be an object.")
        metric_key = item.get("metric_key")
        operator = item.get("operator")
        if not isinstance(metric_key, str) or not metric_key.strip():
            raise AutoresearchError(f"{field_name}[{index}].metric_key must be a non-empty string.")
        if operator not in VALID_OPERATORS:
            raise AutoresearchError(
                f"{field_name}[{index}].operator must be one of {sorted(VALID_OPERATORS)!r}."
            )
        if "target" not in item:
            raise AutoresearchError(f"{field_name}[{index}].target is required.")
        normalized.append(
            {
                "metric_key": metric_key.strip(),
                "operator": operator,
                "target": parse_decimal(item["target"], f"{field_name}[{index}].target"),
            }
        )
    return normalized


def criteria_metric_keys(criteria: Any, *, field_name: str) -> set[str]:
    return {item["metric_key"] for item in parse_criteria(criteria, field_name=field_name)}


def required_metric_keys(config: dict[str, Any]) -> set[str]:
    primary_metric_key = str(config.get("primary_metric_key") or config.get("metric") or "metric").strip()
    keys = {primary_metric_key}
    keys |= criteria_metric_keys(config.get("acceptance_criteria"), field_name="acceptance_criteria")
    keys |= criteria_metric_keys(config.get("required_keep_criteria"), field_name="required_keep_criteria")
    return {key for key in keys if key}


def normalize_criteria_config(criteria: Any, *, field_name: str) -> list[dict[str, Any]]:
    return [
        {
            "metric_key": item["metric_key"],
            "operator": item["operator"],
            "target": decimal_to_json_number(item["target"]),
        }
        for item in parse_criteria(criteria, field_name=field_name)
    ]


def parse_metrics_json_output(raw: str | None, *, field_name: str) -> dict[str, Any] | None:
    if raw in (None, ""):
        return None
    text = str(raw)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    final_line = lines[-1]
    try:
        payload = json.loads(final_line)
    except json.JSONDecodeError as exc:
        raise AutoresearchError(
            f"Invalid JSON for {field_name}: the final non-empty verify output line must be a JSON object."
        ) from exc
    if not isinstance(payload, dict):
        raise AutoresearchError(f"{field_name} final JSON line must be a JSON object.")
    return payload


def normalize_metrics(
    metrics: Any,
    *,
    primary_metric_key: str,
    primary_metric: Any,
    metric_name: str | None = None,
    verify_format: str = "scalar",
    required_keys: set[str] | None = None,
) -> dict[str, Decimal]:
    verify_format = verify_format or "scalar"
    if verify_format not in {"scalar", "metrics_json"}:
        raise AutoresearchError(
            f"Unsupported verify_format {verify_format!r}; expected 'scalar' or 'metrics_json'."
        )

    normalized: dict[str, Decimal] = {}
    if isinstance(metrics, dict):
        for key, value in metrics.items():
            if not isinstance(key, str) or not key.strip():
                continue
            normalized[key.strip()] = parse_decimal(value, f"metric {key!r}")

    primary_value = parse_decimal(primary_metric, primary_metric_key)

    if verify_format == "metrics_json":
        if not isinstance(metrics, dict):
            raise AutoresearchError("verify_format=metrics_json requires --metrics-json with a JSON object.")
        missing = sorted((required_keys or {primary_metric_key}) - normalized.keys())
        if missing:
            raise AutoresearchError(
                "verify_format=metrics_json requires metrics keys: " + ", ".join(missing)
            )
        actual_primary = normalized[primary_metric_key]
        if actual_primary != primary_value:
            raise AutoresearchError(
                f"Primary metric mismatch: --metric is {primary_value}, "
                f"but metrics_json[{primary_metric_key!r}] is {actual_primary}."
            )
        return normalized

    normalized.setdefault(primary_metric_key, primary_value)
    if metric_name and metric_name not in normalized:
        normalized[metric_name] = primary_value
    return normalized


def serialize_metrics(metrics: dict[str, Decimal]) -> dict[str, int | float]:
    return {key: decimal_to_json_number(value) for key, value in metrics.items()}


def criterion_matches(actual: Decimal, expected: Decimal, operator: str) -> bool:
    if operator == "<":
        return actual < expected
    if operator == "<=":
        return actual <= expected
    if operator == ">":
        return actual > expected
    if operator == ">=":
        return actual >= expected
    if operator == "==":
        return actual == expected
    raise AutoresearchError(f"Unsupported operator: {operator!r}")


def evaluate_criteria(
    criteria: Any,
    metrics: dict[str, Decimal],
    *,
    field_name: str,
) -> tuple[bool, list[str]]:
    normalized = parse_criteria(criteria, field_name=field_name)
    failures: list[str] = []
    for item in normalized:
        metric_name = item["metric_key"]
        actual = metrics.get(metric_name)
        if actual is None:
            failures.append(f"{metric_name} missing")
            continue
        if not criterion_matches(actual, item["target"], item["operator"]):
            failures.append(
                f"{metric_name} {item['operator']} {item['target']} (actual {actual})"
            )
    return not failures, failures


def acceptance_state(
    *,
    config: dict[str, Any],
    metric: Any,
    metrics: Any = None,
) -> dict[str, Any]:
    primary_metric_key = str(config.get("primary_metric_key") or config.get("metric") or "metric")
    verify_format = str(config.get("verify_format") or "scalar")
    metrics_map = normalize_metrics(
        metrics,
        primary_metric_key=primary_metric_key,
        primary_metric=metric,
        metric_name=str(config.get("metric") or "").strip() or None,
        verify_format=verify_format,
        required_keys=required_metric_keys(config),
    )
    acceptance_ok, acceptance_failures = evaluate_criteria(
        config.get("acceptance_criteria"),
        metrics_map,
        field_name="acceptance_criteria",
    )
    required_keep_ok, required_keep_failures = evaluate_criteria(
        config.get("required_keep_criteria"),
        metrics_map,
        field_name="required_keep_criteria",
    )
    return {
        "metrics": metrics_map,
        "acceptance_satisfied": acceptance_ok,
        "acceptance_failures": acceptance_failures,
        "required_keep_satisfied": required_keep_ok,
        "required_keep_failures": required_keep_failures,
    }


def retention_is_preferred(
    *,
    direction: str,
    current_metric: Decimal,
    current_acceptance: bool,
    trial_metric: Decimal,
    trial_acceptance: bool,
) -> bool:
    if current_acceptance and not trial_acceptance:
        return False
    if trial_acceptance and not current_acceptance:
        return True
    return improvement(trial_metric, current_metric, direction)
