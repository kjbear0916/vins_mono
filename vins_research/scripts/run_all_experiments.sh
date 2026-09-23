#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# run_all_experiments.sh — Run the full experimental matrix
#
# 3 light levels × 3 speeds × 2 trajectories × 3 repeats = 54 runs
# ═══════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

LIGHTS=("high" "medium" "low")
SPEEDS=("0.5" "1.5" "3.0")
TRAJECTORIES=("circle" "figure8")
REPEATS=(1 2 3)

TOTAL=$((${#LIGHTS[@]} * ${#SPEEDS[@]} * ${#TRAJECTORIES[@]} * ${#REPEATS[@]}))
CURRENT=0

echo "Starting full experiment matrix: ${TOTAL} runs"
echo ""

for light in "${LIGHTS[@]}"; do
  for speed in "${SPEEDS[@]}"; do
    for traj in "${TRAJECTORIES[@]}"; do
      for rep in "${REPEATS[@]}"; do
        CURRENT=$((CURRENT + 1))
        echo "════════════════════════════════════════"
        echo "Run ${CURRENT}/${TOTAL}"
        echo "════════════════════════════════════════"

        "${SCRIPT_DIR}/run_experiment.sh" "${light}" "${speed}" "${traj}" "${rep}"

        echo ""
        echo "Completed run ${CURRENT}/${TOTAL}"
        echo "Waiting 5s before next run..."
        sleep 5
      done
    done
  done
done

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  ALL ${TOTAL} EXPERIMENTS COMPLETE!         ║"
echo "╚══════════════════════════════════════════╝"
