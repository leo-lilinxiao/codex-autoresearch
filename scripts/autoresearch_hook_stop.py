#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys

from autoresearch_core import json_dumps
from autoresearch_hook_context import update_hook_context_pointer
from autoresearch_hook_common import build_context


NONTERMINAL_DECISIONS = {"relaunch", "continue"}
CONTINUATION_PROMPT = (
    "Continue the current autoresearch run.\n"
    "Do not rerun the wizard.\n"
    "If you just completed an experiment, record it before starting the next one.\n"
    "Keep going until the goal is reached, the user stops you, the configured iteration cap is reached, or a true blocker appears."
)
FOLLOWUP_CONTINUATION_PROMPT = (
    "Continue the current autoresearch run.\n"
    "You are already inside a stop-hook continuation.\n"
    "Do not stop yet; if you just completed an experiment, record it before the next one."
)


def run_supervisor(context) -> dict[str, object] | None:
    if context.helper_root is None:
        return None
    if context.artifacts.results_path is None:
        return None
    helper = context.helper_root / "autoresearch_supervisor_status.py"
    command = [
        sys.executable,
        str(helper),
        "--repo",
        str(context.repo),
        "--results-path",
        str(context.artifacts.results_path),
    ]
    if context.artifacts.state_path is not None:
        command.extend(["--state-path", str(context.artifacts.state_path)])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=context.repo,
    )
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def emit_block(reason: str) -> None:
    payload = {
        "decision": "block",
        "reason": reason,
    }
    print(json_dumps(payload), end="")


def main() -> int:
    context = build_context(__file__)
    if context is None or context.helper_root is None:
        return 0
    if not context.session_is_autoresearch:
        return 0
    if not context.has_active_artifacts:
        return 0

    supervisor = run_supervisor(context)
    if supervisor is None:
        return 0

    decision = supervisor.get("decision")
    if not isinstance(decision, str):
        return 0

    if decision in NONTERMINAL_DECISIONS:
        active = bool(context.payload.get("stop_hook_active"))
        emit_block(FOLLOWUP_CONTINUATION_PROMPT if active else CONTINUATION_PROMPT)
    else:
        update_hook_context_pointer(
            repo=context.repo,
            active=False,
            session_mode="background" if context.opt_in_env else "foreground",
            results_path=context.artifacts.results_path,
            state_path=context.artifacts.state_path,
            launch_path=context.artifacts.launch_path,
            runtime_path=context.artifacts.runtime_path,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
