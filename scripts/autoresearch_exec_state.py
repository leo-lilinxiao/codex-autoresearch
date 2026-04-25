#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from autoresearch_core import print_json
from autoresearch_helpers import cleanup_exec_state, default_exec_state_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print or clean the deterministic exec scratch-state path."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root used to derive the deterministic scratch-state path.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove the scratch state file and prune empty temp directories.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured JSON instead of a plain path string.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    if args.cleanup:
        state_path, removed = cleanup_exec_state(repo_root)
        payload = {"removed": removed, "state_path": str(state_path)}
        if args.json:
            print_json(payload)
        else:
            print(state_path)
        return 0

    state_path = default_exec_state_path(repo_root)
    if args.json:
        print_json({"state_path": str(state_path)})
    else:
        print(state_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
