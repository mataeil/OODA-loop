#!/usr/bin/env bash
# Official E2E entrypoint.
#   tests/e2e/run.sh           → build + run the isolated Docker suite
#   tests/e2e/run.sh --local   → same suite directly on the host (no Docker)
set -euo pipefail
cd "$(dirname "$0")/../.."

if [[ "${1:-}" == "--local" ]]; then
  echo "=== Tier 0: static verify ==="
  python3 tests/verify.py
  echo "=== Tier 1: E2E rail scenarios (local) ==="
  exec python3 -m unittest discover -s tests/e2e/scenarios -v
fi

docker build -t ooda-e2e -f tests/e2e/Dockerfile .
exec docker run --rm ooda-e2e
