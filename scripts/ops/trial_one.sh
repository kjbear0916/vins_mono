#!/bin/bash
# trial_one.sh — single end-to-end VINS experiment: fly + record + evaluate.
# Uses repo (mounted) flight scripts so codex/param fixes are picked up.
# Usage: trial_one.sh <light> <traj> <speed> <radius> <alt> <flight_dur> <repeat>
set +e
LIGHT=${1:-sim}
TRAJ=${2:-circle}
SPEED=${3:-1.5}
RADIUS=${4:-5.0}
ALT=${5:-3.0}
DUR=${6:-45}
REPEAT=${7:-1}
RUN_TAG=${8:-}
REC_DUR=$((DUR + 40))
REPO=/root/catkin_ws/src/vins_research
VINS_WORLD=${VINS_WORLD:-vins_demo}
export VINS_WORLD
# Canonical trial id; RUN_TAG (8th arg) namespaces reruns so a repeat never
# overwrites the bag / result dir of an earlier run (e.g. ..._r1_rep2).
TRIAL_ID="${LIGHT}_${SPEED}ms_${TRAJ}_r${REPEAT}${RUN_TAG:+_${RUN_TAG}}"
export TRIAL_ID
# IMU stream rate for this trial (item #12); default 50 Hz so any run without
# an explicit override stays on the baseline arm. Applied by sim_launch.sh.
export IMU_HZ=${IMU_HZ:-50}

source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export HEADLESS=1 NO_PXH=1
unset DISPLAY

BAG=/data/rosbags/${TRIAL_ID}.bag
# Honour VINS_RESULTS_DIR so a re-matrix writes its trial dirs into the same
# tree the batch orchestrator reads (defaults to the master /data/results).
RES=${VINS_RESULTS_DIR:-/data/results}/trial_${TRIAL_ID}
LOG=/tmp/trial_${TRIAL_ID}.log
VINS_LOG=/tmp/vins_${TRIAL_ID}.log
FT_LOG=/tmp/ft_${TRIAL_ID}.log
START=$SECONDS
: > "$LOG"

stop_record() {
  pkill -INT -f 'rosbag recor[d]' 2>/dev/null
  # rosbag record finalizes the bag and removes <bag>.active on a clean SIGINT,
  # so poll for that file (and the process) disappearing instead of a fixed sleep.
  # High-rate IMU (item #12) leaves a large write backlog on the slow drvfs mount,
  # so allow a generous window before any destructive action (obs: 20 s + rm .active
  # was destroying the bag -> bag_unindexable).
  for i in $(seq 1 90); do
    if [ ! -e "${BAG}.active" ] && ! pgrep -f 'rosbag recor[d]' >/dev/null 2>&1; then break; fi
    sleep 1
  done
  if pgrep -f 'rosbag recor[d]' >/dev/null 2>&1; then
    echo "WARN rosbag still active after 90s; hard-killing" | tee -a "$LOG"
    pkill -9 -f 'rosbag recor[d]' 2>/dev/null
  fi
  # Never delete .active when the finalized .bag is absent — that destroys the only
  # copy and forecloses rosbag reindex. Keep it so the caller can attempt recovery.
  if [ -e "${BAG}" ] && [ -e "${BAG}.active" ]; then rm -f "${BAG}.active"; fi
  echo "BAG_STATE: $(ls -la "${BAG}" "${BAG}.active" 2>&1 | tr '\n' '|')" | tee -a "$LOG"
  sleep 1
}

kill_chain() {
  stop_record
  pkill -9 -x px4 2>/dev/null
  pkill -9 -x gzserver 2>/dev/null
  pkill -9 -x Xvfb 2>/dev/null
  pkill -9 -f 'xvfb-ru[n]' 2>/dev/null
  pkill -9 -f 'sitl_run.s[h]' 2>/dev/null
  pkill -9 -x mavros_node 2>/dev/null
  pkill -9 -f 'roslaunc[h]' 2>/dev/null
  pkill -9 -x vins_estimator 2>/dev/null
  pkill -9 -x feature_tracker 2>/dev/null
  pkill -9 -f 'waypoint_fl[ight]' 2>/dev/null
  pkill -9 -f 'mavlink_ar[m]' 2>/dev/null
  pkill -9 -f 'rosbag recor[d]' 2>/dev/null
  sleep 2
}

wait_hz() {
  local topic=$1 min=$2 maxt=$3
  for ((i = 0; i < maxt; i++)); do
    r=$(timeout 7 rostopic hz "$topic" 2>/dev/null | awk '/average rate/ {print $3; exit}')
    if [ -n "$r" ]; then
      got=$(awk -v v="$r" -v m="$min" 'BEGIN{print (v+0>=m)?1:0}')
      if [ "$got" = "1" ]; then echo "READY $topic rate=$r" | tee -a "$LOG"; return 0; fi
    fi
    sleep 1
  done
  echo "FAIL_WAIT $topic" | tee -a "$LOG"
  return 1
}

echo "=== TRIAL $TRIAL_ID $LIGHT ${SPEED}ms $TRAJ r$REPEAT dur=$DUR world=$VINS_WORLD ===" | tee -a "$LOG"
rm -f "$BAG"
rm -f "$BAG.active"
kill_chain

# --- preflight: after kill_chain the host must be clean. A non-zero sim/ROS
#     process count means a concurrent chain or an unkillable zombie; abort and
#     mark rather than record onto a polluted host (2026-10-10: ~80 orphaned
#     gzserver from duplicate chains made every bag_unindexable).
#     Zombies (stat=Z, e.g. bash-as-PID1 orphans) are counted as clean: they are
#     already dead and only awaiting a reap. ---
_n_sim=$(ps -eo stat,comm | awk 'substr($1,1,1)!="Z" && ($2=="gzserver"||$2=="mavros_node"||$2=="px4")' | wc -l)
_n_ros=$(ps -eo stat,args | awk 'substr($1,1,1)!="Z" && ($0 ~ /[s]itl_run\.sh|[f]eature_tracker|[v]ins_estimator/)' | wc -l)
STALE=$((_n_sim + _n_ros))
if [ "$STALE" -gt 0 ]; then
  echo "RESULT FAIL stale_procs sim=$_n_sim ros=$_n_ros" | tee -a "$LOG"
  echo "TRIAL_DONE"
  exit 1
fi

if ! timeout 4 rostopic list >/dev/null 2>&1; then
  nohup roscore >/tmp/roscore.log 2>&1 &
  sleep 6
fi
timeout 3 rostopic list >/dev/null 2>&1 || { echo "RESULT FAIL roscore"; exit 1; }

nohup bash "$REPO/docker/sim_launch.sh" >/tmp/sim.log 2>&1 &
wait_hz /iris_fpv_cam/usb_cam/image_raw 5 60 || { echo "RESULT FAIL sim_camera"; exit 1; }

nohup roslaunch /root/catkin_ws/src/mavros/mavros/launch/px4.launch \
  fcu_url:=udp://:14540@127.0.0.1:14580 >/tmp/mavros.log 2>&1 &
wait_hz /mavros/imu/data_raw 40 40 || { echo "RESULT FAIL mavros_imu"; exit 1; }

nohup rosrun feature_tracker feature_tracker \
  _config_file:=$REPO/config/sim_config.yaml \
  _vins_folder:=$REPO/../VINS-Mono >"$FT_LOG" 2>&1 &
nohup rosrun vins_estimator vins_estimator \
  _config_file:=$REPO/config/sim_config.yaml \
  _vins_folder:=$REPO/../VINS-Mono >"$VINS_LOG" 2>&1 &
sleep 10

nohup rosbag record -O "$BAG" \
  /vins_estimator/path /vins_estimator/odometry \
  /gazebo/model_states /iris_fpv_cam/usb_cam/image_raw \
  /mavros/imu/data_raw /mavros/local_position/pose \
  --duration "$REC_DUR" >/tmp/rec.log 2>&1 &
sleep 3

# --- flight: init-maneuver stream first, arm mid-stream, then circle ---
timeout 60 python3 -u "$REPO/scripts/flight/init_motion.py" >/tmp/initm.log 2>&1 &
INITPID=$!
sleep 6
timeout 90 python3 -u "$REPO/scripts/flight/mavlink_arm.py" >/tmp/arm.log 2>&1
echo "ARM_TAIL: $(tail -3 /tmp/arm.log | tr '\n' '|')" | tee -a "$LOG"
INIT_ENDED=$?
wait "$INITPID"
echo "INITM_TAIL: $(tail -2 /tmp/initm.log | tr '\n' '|')" | tee -a "$LOG"

FLIGHT_TIMEOUT=$((DUR + 90))
timeout "$FLIGHT_TIMEOUT" python3 -u "$REPO/scripts/flight/waypoint_flight.py" --pre-armed \
  --trajectory "$TRAJ" --speed "$SPEED" --radius "$RADIUS" \
  --altitude "$ALT" --duration "$DUR" >/tmp/fly.log 2>&1 &
WPPID=$!

while kill -0 "$WPPID" 2>/dev/null; do sleep 5; done
echo "FLY_TAIL: $(tail -3 /tmp/fly.log | tr '\n' '|')" | tee -a "$LOG"
sleep 20

kill_chain

# --- check bag indexing (reindex only when info fails; verify; drop .orig) ---
if ! rosbag info "$BAG" >/dev/null 2>&1; then
  echo "Reindexing bag: $BAG" | tee -a "$LOG"
  rosbag reindex "$BAG" 2>&1 | tail -5 | tee -a "$LOG"
  if rosbag info "$BAG" >/dev/null 2>&1; then
    rm -f "$BAG.orig.bag"
  else
    echo "RESULT FAIL bag_unindexable $BAG" | tee -a "$LOG"
    echo "TRIAL_DONE"
    exit 1
  fi
fi

# --- bag z-profile (flight truth) + VINS diagnostics ---
echo "=== bag z profile ===" | tee -a "$LOG"
if [ -f "$REPO/scripts/analysis/realbag_z.py" ]; then
  python3 "$REPO/scripts/analysis/realbag_z.py" "$BAG" 2>&1 | head -26 | tee -a "$LOG"
else
  echo "GT_Z unavailable (realbag_z.py missing under $REPO/scripts/analysis/)" | tee -a "$LOG"
fi
echo "=== VINS log tail ===" | tee -a "$LOG"
tail -6 "$VINS_LOG" | cut -c1-130 | tee -a "$LOG"

# --- evaluation closure ---
mkdir -p "$RES"

# --- provenance manifest: md5 of every input that determines the result ---
_md5() { [ -f "$1" ] && md5sum "$1" 2>/dev/null | awk '{print $1}'; }
_px4_world=$(find /root/PX4-Autopilot -name "${VINS_WORLD}.world" 2>/dev/null | head -1)
cat > "$RES/manifest.json" <<MANIFEST
{
  "trial_id": "${TRIAL_ID}",
  "run_tag": "${RUN_TAG}",
  "light": "${LIGHT}",
  "speed": "${SPEED}",
  "trajectory": "${TRAJ}",
  "repeat": "${REPEAT}",
  "vins_world": "${VINS_WORLD}",
  "imu_hz": "${IMU_HZ}",
  "md5": {
    "config/sim_config.yaml": "$(_md5 "$REPO/config/sim_config.yaml")",
    "docker/sim_launch.sh": "$(_md5 "$REPO/docker/sim_launch.sh")",
    "worlds/light_${LIGHT}.world": "$(_md5 "$REPO/worlds/light_${LIGHT}.world")",
    "px4_world/${VINS_WORLD}.world": "$(_md5 "$_px4_world")"
  }
}
MANIFEST

python3 "$REPO/scripts/evaluation/extract_trajectories.py" \
  --bag "$BAG" --output-dir "$RES/trajectories" 2>&1 | tail -4 | tee -a "$LOG"
EVAL_OUT=/tmp/eval_all.out
bash "$REPO/scripts/evaluation/evaluate_all.sh" /data/rosbags "$RES" "${TRIAL_ID}" >"$EVAL_OUT" 2>&1
EVAL_RC=$?
grep -aE 'ATE RMSE|summary' "$EVAL_OUT" | tee -a "$LOG"
if [ "$EVAL_RC" -ne 0 ]; then
  echo "RESULT FAIL eval rc=$EVAL_RC" | tee -a "$LOG"
  echo "TRIAL_DONE"
  exit 1
fi

# --- Sim3 scale / path ratio from the produced trajectories ---
_v=$(ls "$RES"/trajectories/*_vins.txt 2>/dev/null | head -1)
_g=$(ls "$RES"/trajectories/*_gt.tum 2>/dev/null | head -1)
if [ -n "$_v" ] && [ -n "$_g" ] && [ -f "$REPO/scripts/analysis/sim3_scale.py" ]; then
  python3 "$REPO/scripts/analysis/sim3_scale.py" "$_g" "$_v" 2>&1 | tee -a "$LOG"
fi

# --- runtime metrics: monotonic elapsed (immune to guest clock jumps; obs #0100),
#     bag sim duration, measured imu rate, RTF ---
END=$SECONDS
WALL=$((END - START))
_bagraw=$(rosbag info "$BAG" 2>/dev/null | awk '/^duration/{print $2; exit}')
_bagdur=$(echo "$_bagraw" | awk -F'[:s]' '{ if(NF>=3) print $1*60+$2; else print $1+0 }')
_imun=$(rosbag info "$BAG" 2>/dev/null | awk '/mavros\/imu\/data_raw/{print $2; exit}')
_imuhz=$(awk -v n="$_imun" -v d="$_bagdur" 'BEGIN{printf "%.2f", (d>0)?n/d:0}')
_rtf=$(awk -v d="$_bagdur" -v w="$WALL" 'BEGIN{printf "%.4f", (w>0)?d/w:0}')
printf 'wall_s,bag_sim_dur_s,imu_hz,rtf\n%s,%s,%s,%s\n' \
  "$WALL" "$_bagdur" "$_imuhz" "$_rtf" > "$RES/metrics.csv"
echo "METRICS wall=${WALL}s sim=${_bagdur}s imu_hz=${_imuhz} rtf=${_rtf}" | tee -a "$LOG"

echo "RESULT done bag=$BAG" | tee -a "$LOG"
echo "SUMCSV:" | tee -a "$LOG"
cat "$RES/summary.csv" 2>/dev/null | tee -a "$LOG"
echo "TRIAL_DONE"