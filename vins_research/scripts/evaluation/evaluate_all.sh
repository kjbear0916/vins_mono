#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# evaluate_all.sh — Run EVO evaluation on all experiment bags
# and produce a summary CSV.
#
# Usage:
#   ./evaluate_all.sh [bag_dir] [result_dir]
#
# Bag naming:
#   <light>_<speed>ms_<traj>_r<N>.bag   (preferred)
#   <traj>_<speed>ms_r<N>.bag           (light = N/A)
# ═══════════════════════════════════════════════════════

set -u

# ROS env for rosbag extraction (silently no-op on hosts without ROS,
# but required wherever .bag files are produced).
source /opt/ros/noetic/setup.bash 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BAG_DIR="${1:-${PROJECT_DIR}/data/rosbags}"
RESULT_DIR="${2:-${PROJECT_DIR}/data/results}"
BAG_PATTERN="${3:-*}"

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

echo "Found ${BAG_COUNT} bags (total)."

# --- loud failure when the pattern matches nothing (single-trial filters
#     must not silently fall through to an empty summary) ---
# BAG_PATTERN may be a bare filename (e.g. high_1.5ms_circle_r1) with no glob
# characters, or a glob like *. Expand once, keep only existing files, and
# exit 3 if nothing matched.
EXPANDED=( "${BAG_DIR}"/${BAG_PATTERN}.bag )
BAGS=()
for b in "${EXPANDED[@]}"; do
    [ -f "${b}" ] && BAGS+=("${b}")
done
MATCH_COUNT=${#BAGS[@]}
if [ "${MATCH_COUNT}" -eq 0 ]; then
    echo "ERROR: no bag matches '${BAG_DIR}/${BAG_PATTERN}.bag'" >&2
    echo "  dir has: $(ls "${BAG_DIR}" 2>/dev/null | head -5 | tr '\n' ' ')" >&2
    exit 3
fi
echo "Matched ${MATCH_COUNT} bag(s) for pattern '${BAG_PATTERN}'."

# --- extract single numeric field from evo result file (pickle w/ persistent ids) ---
stat_field() {
  python3 -c "
from evo.tools import file_interface
try:
    d = file_interface.load_res_file('${1}')
    print(d.stats['${2}'])
except Exception:
    import sys; sys.exit(1)
" 2>/dev/null || echo "N/A"
}

INDEX=0
FAILED=0
for BAG in "${BAGS[@]}"; do
    BASENAME=$(basename "${BAG}" .bag)
    if [[ "${BASENAME}" == *".orig"* ]] || [[ "${BASENAME}" == *"bak"* ]]; then
        continue
    fi
    INDEX=$((INDEX + 1))
    echo ""
    echo "[${INDEX}/${MATCH_COUNT}] Processing: ${BASENAME}"

    # ─── Parse experiment ID: <light>_<speed>ms_<traj>_r<N> ───
    NF=$(awk -F'_' '{print NF}' <<< "${BASENAME}")
    if [ "${NF}" -ge 4 ]; then
        IFS='_' read -r LIGHT SPEED_MS TRAJ REPEAT <<< "${BASENAME}"
        SPEED="${SPEED_MS%ms}"
    elif [ "${NF}" -ge 3 ]; then
        IFS='_' read -r TRAJ SPEED_MS REPEAT <<< "${BASENAME}"
        LIGHT="N/A"
        SPEED="${SPEED_MS%ms}"
    else
        echo "    ERROR: cannot parse experiment id from '${BASENAME}'; use <light>_<speed>ms_<traj>_r<N>"
        continue
    fi
    echo "    light=${LIGHT} speed=${SPEED}ms traj=${TRAJ} repeat=${REPEAT}"

    # ─── Extract trajectories ───
    TRAJ_VINS="${TRAJ_DIR}/${BASENAME}_vins.txt"
    TRAJ_GT="${TRAJ_DIR}/${BASENAME}_gt.tum"

    python3 "${SCRIPT_DIR}/extract_trajectories.py" \
        --bag "${BAG}" \
        --output-dir "${TRAJ_DIR}"

    N_VINS=$(wc -l < "${TRAJ_VINS}" 2>/dev/null || echo 0)
    N_GT=$(wc -l < "${TRAJ_GT}" 2>/dev/null || echo 0)
    if [ "${N_GT}" -lt 10 ]; then
        echo "    ERROR: ground-truth extraction failed (${N_GT} rows)"
        echo "${LIGHT},${SPEED},${TRAJ},${REPEAT},N/A,N/A,N/A,N/A,N/A,N/A,N/A,gt_empty_${N_GT}" >> "${CSV_OUT}"
        FAILED=$((FAILED + 1))
        continue
    fi
    if [ "${N_VINS}" -lt 10 ]; then
        echo "    WARN: VINS trajectory empty (${N_VINS} rows); writing N/A row"
        echo "${LIGHT},${SPEED},${TRAJ},${REPEAT},N/A,N/A,N/A,N/A,N/A,N/A,N/A,vins_empty_${N_VINS}" >> "${CSV_OUT}"
        FAILED=$((FAILED + 1))
        continue
    fi

    # ─── Run EVO APE (ATE) ───
    echo "    Computing ATE..."
    ATE_JSON="${EVO_DIR}/${BASENAME}_ape.json"
    rm -f "${ATE_JSON}"   # evo prompts interactively on overwrite; crash in batch
    evo_ape tum "${TRAJ_GT}" "${TRAJ_VINS}" \
        -a -r full \
        --save_results "${ATE_JSON}" > /dev/null 2>&1
    ATE_RMS=$(stat_field "${ATE_JSON}" rmse)
    ATE_MEDIAN=$(stat_field "${ATE_JSON}" median)
    ATE_MEAN=$(stat_field "${ATE_JSON}" mean)
    ATE_STD=$(stat_field "${ATE_JSON}" std)
    ATE_MAX=$(stat_field "${ATE_JSON}" max)

    # ─── Run EVO RPE ───
    echo "    Computing RPE..."
    RPE_JSON="${EVO_DIR}/${BASENAME}_rpe.json"
    rm -f "${RPE_JSON}"
    evo_rpe tum "${TRAJ_GT}" "${TRAJ_VINS}" \
        -a -r trans_part \
        --save_results "${RPE_JSON}" > /dev/null 2>&1
    RPE_RMS=$(stat_field "${RPE_JSON}" rmse)
    RPE_MEAN=$(stat_field "${RPE_JSON}" mean)

    # ─── Write to CSV ───
    if [ "${ATE_RMS}" = "N/A" ]; then
        NOTE="evo_ate_failed"
        FAILED=$((FAILED + 1))
    else
        NOTE="ok"
    fi
    echo "${LIGHT},${SPEED},${TRAJ},${REPEAT},${ATE_RMS},${ATE_MEDIAN},${ATE_MEAN},${ATE_STD},${ATE_MAX},${RPE_RMS},${RPE_MEAN},${NOTE}" >> "${CSV_OUT}"

    echo "    ATE RMSE: ${ATE_RMS} m | RPE RMSE: ${RPE_RMS} m"
done

if [ "${FAILED}" -gt 0 ]; then
    echo "ERROR: ${FAILED} bag(s) failed evaluation" >&2
    exit 4
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Evaluation complete!                     ║"
echo "║  Summary CSV: ${CSV_OUT}"
echo "╚══════════════════════════════════════════╝"