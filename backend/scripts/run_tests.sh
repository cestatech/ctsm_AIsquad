#!/usr/bin/env bash
# Run backend tests with unbuffered progress output.
# Usage:
#   ./scripts/run_tests.sh          # unit + integration
#   ./scripts/run_tests.sh unit     # unit only
#   ./scripts/run_tests.sh integration

set -euo pipefail

cd "$(dirname "$0")/.."

export APP_ENV="${APP_ENV:-development}"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://celerius:celerius@localhost:5432/celerius_test}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export APP_SECRET_KEY="${APP_SECRET_KEY:-test-secret-key-for-local-only-32chars}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-test-jwt-secret-for-local-only-32chars}"
export STORAGE_BACKEND="${STORAGE_BACKEND:-filesystem}"
export STORAGE_LOCAL_PATH="${STORAGE_LOCAL_PATH:-/tmp/celerius-test-storage}"

PYTEST=(.venv/bin/pytest)
if [[ ! -x "${PYTEST[0]}" ]]; then
  PYTEST=(pytest)
fi

run_unit() {
  echo "==> Backend unit tests"
  PYTHONUNBUFFERED=1 "${PYTEST[@]}" tests/unit -q --tb=short --durations=10
}

run_integration() {
  echo "==> Backend integration tests"
  PYTHONUNBUFFERED=1 "${PYTEST[@]}" tests/integration -q --tb=short --durations=15
}

case "${1:-all}" in
  unit) run_unit ;;
  integration) run_integration ;;
  all)
    run_unit
    run_integration
    ;;
  *)
    echo "Unknown target: ${1}" >&2
    echo "Usage: $0 [unit|integration|all]" >&2
    exit 1
    ;;
esac
