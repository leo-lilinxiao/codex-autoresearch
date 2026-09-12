#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 -m unittest discover -s "$ROOT/tests" -p 'test_structure.py' -q
echo "Skill structure valid."
