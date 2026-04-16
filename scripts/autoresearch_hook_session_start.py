#!/usr/bin/env python3
from __future__ import annotations

from autoresearch_core import json_dumps
from autoresearch_hook_common import build_context


CHECKLIST_LINES = (
    "- If this is a fresh run, baseline first, then initialize results/state artifacts.",
    "- Record every completed experiment before starting the next one.",
    "- Use helper scripts for authoritative TSV/state updates.",
    "- Do not rerun the wizard after launch is already confirmed.",
)


def emit_additional_context(text: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }
    print(json_dumps(payload), end="")


def main() -> int:
    context = build_context(__file__)
    if context is None:
        return 0
    if not context.session_is_autoresearch:
        return 0
    if not context.has_active_artifacts:
        return 0

    emit_additional_context("\n".join(CHECKLIST_LINES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
