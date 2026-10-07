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
REC_DUR=$((DUR + 40))
REPO=/root/catkin_ws/src/vins_research
VINS_WORLD=${VINS_WORLD:-vins_demo}
export VINS_WORLD

source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export HEADLESS=1 NO_PXH=1
unset DISPLAY

BAG=/data/rosbags/${LIGHT}_${SPEED}ms_${TRAJ}_r${REPEAT}.bag
RES=/data/results/trial_${LIGHT}_${SPEED}ms_${TRAJ}_r${REPEAT}
LOG=/tmp/trial.log
: > "$LOG"

stop_record() {
  pkill -INT -f 'rosbag recor[d]' 2>/dev/null
  for i in $(seq 1 15); do pgrep -f 'rosbag recor[d]' >/dev/null 2>&1 || break; sleep 1; done
  pkill -9 -f 'rosbag recor[d]' 2>/dev/null
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

echo "=== TRIAL $LIGHT ${SPEED}ms $TRAJ r$REPEAT dur=$DUR ===" | tee -a "$LOG"
rm -f "$BAG"
kill_chain

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
  _vins_folder:=$REPO/../VINS-Mono >/tmp/ft.log 2>&1 &
nohup rosrun vins_estimator vins_estimator \
  _config_file:=$REPO/config/sim_config.yaml \
  _vins_folder:=$REPO/../VINS-Mono >/tmp/vins.log 2>&1 &
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

# --- check bag indexing ---
if ! rosbag info "$BAG" >/dev/null 2>&1; then
  echo "Reindexing bag: $BAG" | tee -a "$LOG"
  rosbag reindex "$BAG" >/dev/null 2>&1 || true
fi

# --- bag z-profile (flight truth) + VINS diagnostics ---
echo "=== bag z profile ===" | tee -a "$LOG"
python3 "$REPO/scripts/analysis/realbag_z.py" "$BAG" 2>&1 | head -26 | tee -a "$LOG"
echo "=== VINS log tail ===" | tee -a "$LOG"
tail -6 /tmp/vins.log | cut -c1-130 | tee -a "$LOG"

# --- evaluation closure ---
mkdir -p "$RES"
python3 "$REPO/scripts/evaluation/extract_trajectories.py" \
  --bag "$BAG" --output-dir "$RES/trajectories" 2>&1 | tail -4 | tee -a "$LOG"
EVAL_OUT=/tmp/eval_all.out
bash "$REPO/scripts/evaluation/evaluate_all.sh" /data/rosbags "$RES" "${LIGHT}_${SPEED}ms_${TRAJ}_r${REPEAT}" >"$EVAL_OUT" 2>&1
EVAL_RC=$?
grep -aE 'ATE RMSE|summary' "$EVAL_OUT" | tee -a "$LOG"
if [ "$EVAL_RC" -ne 0 ]; then
  echo "RESULT FAIL eval rc=$EVAL_RC" | tee -a "$LOG"
  echo "TRIAL_DONE"
  exit 1
fi
echo "RESULT done bag=$BAG" | tee -a "$LOG"
echo "SUMCSV:" | tee -a "$LOG"
cat "$RES/summary.csv" 2>/dev/null | tee -a "$LOG"
echo "TRIAL_DONE"