#!/usr/bin/env bash
set -euo pipefail

if [ ! -f uv.lock ]; then
  echo "Error: uv.lock is missing. Run 'uv lock' or 'uv sync' to generate it." >&2
  exit 1
fi

if ! git ls-files --error-unmatch uv.lock >/dev/null 2>&1; then
  echo "Error: uv.lock is not tracked by git. Add it with 'git add uv.lock'." >&2
  exit 1
fi

echo "uv.lock is present and tracked."
