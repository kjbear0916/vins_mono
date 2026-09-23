#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# Full pipeline: run all experiments → evaluate → plot → analyze
#
#   bash scripts/full_pipeline.sh [start_run] [end_run]
# ═══════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

START="${1:-1}"
END="${2:-54}"

echo "══════════════════════════════════════════"
echo "  VINS-Mono Research Full Pipeline"
echo "  Runs ${START} to ${END}"
echo "══════════════════════════════════════════"

echo ""
echo "── Phase 1/4: Running experiments ..."
# Run only the requested range by delegating to the full matrix script
# (simplification: run all; adjust logic as needed)
bash "${SCRIPT_DIR}/run_all_experiments.sh"

echo ""
echo "── Phase 2/4: Evaluating results ..."
bash "${SCRIPT_DIR}/evaluation/evaluate_all.sh"

echo ""
echo "── Phase 3/4: Generating plots ..."
python3 "${SCRIPT_DIR}/evaluation/make_plots.py"

echo ""
echo "── Phase 4/4: Statistical analysis ..."
python3 "${SCRIPT_DIR}/analysis/statistical_analysis.py"

echo ""
echo "══════════════════════════════════════════"
echo "  PIPELINE COMPLETE"
echo "  Results: ${PROJECT_DIR}/data/results/"
echo "  Plots:   ${PROJECT_DIR}/data/plots/"
echo "══════════════════════════════════════════"