#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# evaluate_all.sh — Run EVO evaluation on all experiment bags
# and produce a summary CSV.
#
# Usage:
#   ./evaluate_all.sh [data/rosbags] [data/results]
# ═══════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BAG_DIR="${1:-${PROJECT_DIR}/data/rosbags}"
RESULT_DIR="${2:-${PROJECT_DIR}/data/results}"

# ─── Paths ───
TRAJ_DIR="${RESULT_DIR}/trajectories"
EVO_DIR="${RESULT_DIR}/evo_metrics"
mkdir -p "${TRAJ_DIR}" "${EVO_DIR}"

CSV_OUT="${RESULT_DIR}/summary.csv"
echo "light,speed,trajectory,repeat,ate_rms,ate_median,ate_mean,ate_std,ate_max,rpe_rms,rpe_mean,features_note" > "${CSV_OUT}"

echo "Evaluating bags in: ${BAG_DIR}"
echo "Results in: ${RESULT_DIR}"

BAG_COUNT=$(ls "${BAG_DIR}"/*.bag 2>/dev/null | wc -l)
if [ "$BAG_COUNT" -eq 0 ]; then
    echo "ERROR: No .bag files found in ${BAG_DIR}"
    exit 1
fi

echo "Found ${BAG_COUNT} bags."

INDEX=0
for BAG in "${BAG_DIR}"/*.bag; do
    INDEX=$((INDEX + 1))
    BASENAME=$(basename "${BAG}" .bag)
    echo ""
    echo "[${INDEX}/${BAG_COUNT}] Processing: ${BASENAME}"

    # ─── Parse experiment ID: light_speedms_trajectory_rN ───
    IFS='_' read -r LIGHT SPEED_MS TRAJ REPEAT <<< "${BASENAME}"
    SPEED="${SPEED_MS%ms}"

    # ─── Extract trajectories ───
    TRAJ_VINS="${TRAJ_DIR}/${BASENAME}_vins.txt"
    TRAJ_GT="${TRAJ_DIR}/${BASENAME}_gt.txt"

    python3 "${SCRIPT_DIR}/extract_trajectories.py" \
        --bag "${BAG}" \
        --output-dir "${TRAJ_DIR}"

    if [ ! -f "${TRAJ_GT}" ] || [ ! -f "${TRAJ_VINS}" ]; then
        echo "ERROR: Trajectory extraction failed for ${BASENAME}"
        continue
    fi

    # ─── Run EVO APE (ATE) ───
    echo "    Computing ATE..."
    ATE_JSON="${EVO_DIR}/${BASENAME}_ape.json"
    evo_ape tum "${TRAJ_GT}" "${TRAJ_VINS}" \
        -a -r full \
        --save_results "${ATE_JSON}" > /dev/null 2>&1

    # Parse ATE metrics from JSON
    ATE_RMS=$(python3 -c "
import json, sys
d = json.load(open('${ATE_JSON}'))
stats = d['statistics']
print(stats['rmse'])
" 2>/dev/null || echo "N/A")
    ATE_MEDIAN=$(python3 -c "
import json, sys
d = json.load(open('${ATE_JSON}'))
stats = d['statistics']
print(stats['median'])
" 2>/dev/null || echo "N/A")
    ATE_MEAN=$(python3 -c "
import json, sys
d = json.load(open('${ATE_JSON}'))
stats = d['statistics']
print(stats['mean'])
" 2>/dev/null || echo "N/A")
    ATE_STD=$(python3 -c "
import json, sys
d = json.load(open('${ATE_JSON}'))
stats = d['statistics']
print(stats['std'])
" 2>/dev/null || echo "N/A")
    ATE_MAX=$(python3 -c "
import json, sys
d = json.load(open('${ATE_JSON}'))
stats = d['statistics']
print(stats['max'])
" 2>/dev/null || echo "N/A")

    # ─── Run EVO RPE ───
    echo "    Computing RPE..."
    RPE_JSON="${EVO_DIR}/${BASENAME}_rpe.json"
    evo_rpe tum "${TRAJ_GT}" "${TRAJ_VINS}" \
        -a -r trans_part \
        --save_results "${RPE_JSON}" > /dev/null 2>&1

    RPE_RMS=$(python3 -c "
import json, sys
d = json.load(open('${RPE_JSON}'))
stats = d['statistics']
print(stats['rmse'])
" 2>/dev/null || echo "N/A")

    # ─── Write to CSV ───
    echo "${LIGHT},${SPEED},${TRAJ},${REPEAT},${ATE_RMS},${ATE_MEDIAN},${ATE_MEAN},${ATE_STD},${ATE_MAX},${RPE_RMS}," >> "${CSV_OUT}"

    echo "    ATE RMSE: ${ATE_RMS} m | RPE RMSE: ${RPE_RMS} m"
done

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Evaluation complete!                     ║"
echo "║  Summary CSV: ${CSV_OUT}"
echo "╚══════════════════════════════════════════╝"