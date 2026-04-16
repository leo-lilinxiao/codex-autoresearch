#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from autoresearch_core import print_json
from autoresearch_helpers import (
    AutoresearchError,
    build_state_payload,
    compare_summary_to_state,
    decimal_to_json_number,
    log_summary,
    parse_log_metadata,
    parse_results_log,
    read_state_payload,
    require_context_for_repo,
    resolve_context_workspace_root,
    resolve_repo_path,
    resolve_repo_relative,
    resolve_state_path_for_log,
    STATE_FILE_NAME,
    write_json_atomic,
)
from autoresearch_workspace import resolve_workspace_root


REQUIRED_RESUME_CONFIG_FIELDS = ("goal", "scope", "metric", "direction", "verify")


def missing_resume_config_fields(config: object) -> list[str]:
    if not isinstance(config, dict):
        return list(REQUIRED_RESUME_CONFIG_FIELDS)

    missing: list[str] = []
    for field_name in ("goal", "scope", "metric", "verify"):
        value = config.get(field_name)
        if not isinstance(value, str) or not value.strip():
            missing.append(field_name)

    direction = config.get("direction")
    if direction not in {"lower", "higher"}:
        missing.append("direction")
    return missing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether a prior run can resume from JSON state, TSV state, or needs a fresh start."
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Primary repo root. Run context is resolved from this repo's git-local pointer.",
    )
    parser.add_argument("--workspace-root")
    parser.add_argument(
        "--results-path",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--state-path",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--write-repaired-state",
        action="store_true",
        help="If TSV recovery is possible, rewrite state.json from the reconstructed TSV state.",
    )
    return parser


def serialize_tsv_summary(reconstructed: dict[str, object] | None) -> dict[str, object] | None:
    if reconstructed is None:
        return None
    return {
        "iteration": reconstructed["iteration"],
        "baseline_metric": decimal_to_json_number(reconstructed["baseline_metric"]),
        "best_metric": decimal_to_json_number(reconstructed["best_metric"]),
        "best_iteration": reconstructed["best_iteration"],
        "current_metric": decimal_to_json_number(reconstructed["current_metric"]),
        "current_labels": list(reconstructed.get("current_labels", [])),
        "last_status": reconstructed["last_status"],
        "last_trial_labels": list(reconstructed.get("last_trial_labels", [])),
        "worker_rows": reconstructed["worker_rows"],
        "main_rows": reconstructed["main_rows"],
    }


def evaluate_resume_state(
    *,
    results_path: Path,
    state_path_arg: str | None,
    default_state_path: Path | None = None,
    write_repaired_state: bool = False,
) -> dict[str, object]:
    results_exists = results_path.exists()
    parsed = None
    reconstructed = None
    direction = None
    tsv_error = None
    metadata: dict[str, str] = {}
    if results_exists:
        try:
            parsed = parse_results_log(results_path)
            metadata = parsed.metadata
            direction = parsed.metadata.get("metric_direction")
            if direction not in {"lower", "higher"}:
                raise AutoresearchError("results log is missing a valid # metric_direction comment")
            reconstructed = log_summary(parsed, direction)
        except AutoresearchError as exc:
            tsv_error = str(exc)
            metadata = parse_log_metadata(results_path)

    state_path = resolve_state_path_for_log(
        state_path_arg,
        parsed or metadata,
        cwd=Path.cwd(),
        default_path=default_state_path,
        results_path=results_path,
    )
    state_exists = state_path.exists()

    state_payload = None
    state_error = None
    if state_exists:
        try:
            state_payload = read_state_payload(state_path)
            config = state_payload.get("config", {})
            missing_config_fields = missing_resume_config_fields(config)
            if missing_config_fields:
                state_error = (
                    "config is missing required resume fields: "
                    + ", ".join(missing_config_fields)
                )
            json_direction = config.get("direction")
            if (
                state_error is None
                and reconstructed is not None
                and json_direction not in {direction, None}
            ):
                state_error = (
                    f"config.direction mismatch between state ({json_direction}) and TSV ({direction})"
                )
        except AutoresearchError as exc:
            state_error = str(exc)

    decision = "fresh_start"
    detail = "fresh_start"
    reasons: list[str] = []

    if reconstructed is not None:
        if state_payload is not None and state_error is None:
            mismatches = compare_summary_to_state(reconstructed, state_payload)
            if mismatches:
                decision = "mini_wizard"
                detail = "state_tsv_diverged"
                reasons.extend(mismatches)
            else:
                decision = "full_resume"
                detail = "json_matches_tsv"
                reasons.append("JSON state matches the reconstructed TSV summary.")
        elif state_payload is not None and state_error is not None:
            decision = "mini_wizard"
            detail = "invalid_state_json"
            reasons.append(f"JSON state needs confirmation: {state_error}")
        else:
            decision = "tsv_fallback"
            detail = "tsv_reconstruction_only"
            if state_exists:
                reasons.append(f"JSON unavailable: {state_error}")
            else:
                reasons.append("No JSON state file; TSV reconstruction is available.")
    elif state_payload is not None:
        decision = "mini_wizard"
        detail = "state_without_reconstructable_tsv" if results_exists else "state_without_results"
        if state_error is not None:
            reasons.append(f"JSON state needs confirmation: {state_error}")
        if tsv_error is not None:
            reasons.append(f"JSON state exists but TSV is unavailable: {tsv_error}")
        elif not results_exists:
            reasons.append("JSON state exists but results log is missing.")
        else:
            reasons.append("JSON state exists but results log could not be reconstructed.")
    elif state_error is not None:
        detail = "unrecoverable_artifacts"
        reasons.append(f"JSON unavailable: {state_error}")
    if tsv_error is not None:
        if not state_exists:
            detail = "unrecoverable_artifacts"
        reasons.append(f"TSV unavailable: {tsv_error}")

    repaired = False
    if (
        write_repaired_state
        and reconstructed is not None
        and decision == "tsv_fallback"
    ):
        source_payload = state_payload or {}
        repaired_payload = build_state_payload(
            mode=source_payload.get("mode", "loop"),
            run_tag=source_payload.get("run_tag") or parsed.metadata.get("run_tag"),
            config=source_payload.get("config", {"direction": direction}),
            summary=reconstructed,
            supervisor=source_payload.get("supervisor"),
        )
        write_json_atomic(state_path, repaired_payload)
        repaired = True
        reasons.append(f"Rewrote {state_path.name} from TSV data.")

    return {
        "decision": decision,
        "detail": detail,
        "results_path": str(results_path),
        "state_path": str(state_path),
        "reasons": reasons,
        "repaired_state": repaired,
        "tsv_summary": serialize_tsv_summary(reconstructed),
        "has_results": results_exists,
        "has_state": state_exists,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo = resolve_repo_path(args.repo)
    if args.results_path is not None:
        workspace_root = (
            resolve_workspace_root(repo, args.workspace_root)
            if args.workspace_root is not None
            else Path.cwd().resolve()
        )
        results_path = resolve_repo_relative(workspace_root, args.results_path, Path(args.results_path))
        state_default = results_path.parent / STATE_FILE_NAME
    else:
        context = require_context_for_repo(repo)
        workspace_root = resolve_context_workspace_root(
            repo=repo,
            context=context,
            raw_workspace_root=args.workspace_root,
        )
        results_path = context.results_path
        state_default = context.state_path
    output = evaluate_resume_state(
        results_path=results_path,
        state_path_arg=args.state_path,
        default_state_path=state_default,
        write_repaired_state=args.write_repaired_state,
    )

    print_json(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
