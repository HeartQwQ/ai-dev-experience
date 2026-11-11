#!/usr/bin/env sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$TASK_ROOT"
TASK_PYTHON=${DEV_SPEC_PYTHON:-}
if [ -z "$TASK_PYTHON" ] && [ -f "$TASK_ROOT/.dev-spec/local/python-executable.txt" ]; then
  TASK_PYTHON=$(cat "$TASK_ROOT/.dev-spec/local/python-executable.txt")
fi
if [ -z "$TASK_PYTHON" ] || [ ! -x "$TASK_PYTHON" ]; then TASK_PYTHON=python3; fi
exec "$TASK_PYTHON" "$TASK_ROOT/tools/dev-spec/dev.py" --root "$TASK_ROOT" "$@"
