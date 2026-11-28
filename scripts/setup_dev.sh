#!/usr/bin/env bash
# Self-sufficient bootstrap for THIS repo (Omni_Pre_Processor) — no suite
# checkout required (OPP#150). Independent mode: THIS repo's uv.lock /
# pyproject only. The joint mode (suite-root uv.lock) is documented in
# AGENTS.md → 运行环境与门禁速查.
#
# Usage:
#   bash scripts/setup_dev.sh                # install + self-check
#   bash scripts/setup_dev.sh --check-only   # verify prerequisites only
set -euo pipefail
cd "$(dirname "$0")/.."

CHECK_ONLY=0
[ "${1:-}" = "--check-only" ] && CHECK_ONLY=1

# uv path (preferred): honors this repo's uv.lock.
if command -v uv >/dev/null 2>&1; then
  if [ "$CHECK_ONLY" = "1" ]; then
    echo "[CHECK-ONLY] uv $(uv --version | head -1) found; sync skipped."
    echo "[OK] $("$(uv python find)" -V)"
    exit 0
  fi
  echo "[INFO] uv found — uv sync --all-extras (independent mode: this repo's uv.lock)"
  uv sync --all-extras
  echo "[OK] $("$(uv python find)" -V)"
  echo "[INFO] Self-check:"
  uv run python -c "import opp; from importlib.metadata import version; print('OK: opp', version('omni-pre-processor'), 'importable')"
  echo "[OK] OPP ready. CLI smoke: OMNI_TEST_FAKE_LLM=1 uv run opp <file> --target-format both --output-dir <dir>"
  exit 0
fi

# venv + pip path (no uv installed).
PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ERROR: neither uv nor python found. Install Python >= 3.13 or uv." >&2
  exit 1
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)' || {
  echo "ERROR: Python >= 3.13 required ($("$PY" -V))." >&2
  exit 1
}
if [ "$CHECK_ONLY" = "1" ]; then
  echo "[CHECK-ONLY] $("$PY" -V) found (no uv); venv creation skipped."
  exit 0
fi

[ -d .venv ] || "$PY" -m venv .venv
if [ -f .venv/bin/python ]; then VPY=.venv/bin/python; else VPY=.venv/Scripts/python.exe; fi
echo "[OK] $("$VPY" -V)"
"$VPY" -m pip install --upgrade pip >/dev/null
"$VPY" -m pip install -e .
echo "[INFO] Self-check:"
"$VPY" -c "import opp; from importlib.metadata import version; print('OK: opp', version('omni-pre-processor'), 'importable')"
echo "[OK] OPP ready. CLI smoke: OMNI_TEST_FAKE_LLM=1 .venv/bin/opp <file> --target-format both --output-dir <dir>"
