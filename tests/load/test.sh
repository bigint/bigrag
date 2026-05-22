#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  . "$SCRIPT_DIR/.env"
  set +a
fi

usage() {
  echo "Usage: ./test.sh <rps>"
}

if [ "$#" -ne 1 ]; then
  usage >&2
  exit 1
fi

exec uv run --project "$ROOT_DIR/api" python "$SCRIPT_DIR/streaming.py" "$1"
