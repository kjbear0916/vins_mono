#!/bin/bash
# run9_variance.sh — item #9: run-to-run variance baseline + world A/B.
#
# One fixed cell (high / 1.5 m/s / circle / r1), one fixed config; the only
# thing that changes between the two arms is VINS_WORLD:
#   arm A  vins_demo   — the world the 54-matrix used  (baseline variance)
#   arm B  vins_plain  — flat/planar world             (props A/B)
# 3 repeats each + the two already-known vins_demo values (0.383 master, 0.495
# rerun) gives n=5 for the baseline arm. n=3 cannot support a significance
# claim; report min/max/mean and the spread only.
#
# Writes one row per run to /data/results/variance9.csv.
set +e
source /opt/ros/noetic/setup.bash 2>/dev/null
source /root/catkin_ws/devel/setup.bash 2>/dev/null
REPO=/root/catkin_ws/src/vins_research
OUT=/data/results/variance9.csv
: > "$OUT"
echo "trial_id,world,ate_rms,sim3_scale,path_ratio,imu_hz,bag_sim_dur_s,wall_s,rtf" >> "$OUT"

run_one() {
  local world=$1 tag=$2
  local freeb
  freeb=$(df -Pm /data 2>/dev/null | awk 'NR==2{print $4}')
  if [ "${freeb:-0}" -lt 1500 ]; then
    echo "[run9] ABORT low disk ${freeb}MB" | tee -a "$OUT"
    return 1
  fi
  local t0
  t0=$(date +%s)
  VINS_WORLD="$world" bash "$REPO/scripts/ops/trial_one.sh" \
      high circle 1.5 5.0 3.0 45 1 "$tag" >"/tmp/run9_${tag}.out" 2>&1
  local t1
  t1=$(date +%s)
  local wall=$((t1 - t0))
  local trial_id="high_1.5ms_circle_r1_${tag}"
  local res="/data/results/trial_${trial_id}"
  local bag="/data/rosbags/${trial_id}.bag"
  local log="/tmp/trial_${trial_id}.log"

  local ate scale ratio bdur imu imu_hz rtf
  ate=$(awk -F, 'NR==2{print $5}' "$res/summary.csv" 2>/dev/null)
  scale=$(grep -ao 'SIM3 scale=[0-9.]*' "$log" 2>/dev/null | head -1 | cut -d= -f2)
  ratio=$(grep -ao 'path_ratio_V/G=[0-9.]*' "$log" 2>/dev/null | head -1 | cut -d= -f2)
  # duration prints as "45.12s" or "1:05s" for >=60s; normalise to seconds.
  local raw
  raw=$(rosbag info "$bag" 2>/dev/null | awk '/^duration/{print $2; exit}')
  bdur=$(echo "$raw" | awk -F'[:s]' '{ if(NF>=3) print $1*60+$2; else print $1+0 }')
  imu=$(rosbag info "$bag" 2>/dev/null | awk '/mavros\/imu\/data_raw/{print $2; exit}')
  imu_hz=$(awk -v n="$imu" -v d="$bdur" 'BEGIN{print (d>0)?n/d:0}')
  rtf=$(awk -v d="$bdur" -v w="$wall" 'BEGIN{print (w>0)?d/w:0}')

  echo "${trial_id},${world},${ate},${scale},${ratio},${imu_hz},${bdur},${wall},${rtf}" >> "$OUT"
  echo "[run9] ${trial_id} ate=${ate} scale=${scale} ratio=${ratio} imu_hz=${imu_hz} rtf=${rtf}"
}

for tag in demo_rep3 demo_rep4 demo_rep5; do run_one vins_demo "$tag"; done
for tag in plain_rep3 plain_rep4 plain_rep5; do run_one vins_plain "$tag"; done
echo "[run9] DONE"
