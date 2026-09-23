#!/bin/bash
# One-trial orchestrator: fresh chain -> fly -> record -> teardown.
# Usage: run_trial.sh TRIAL TRAJ SPEED RADIUS ALT FLIGHT_DUR
set +e

TRIAL=$1
TRAJ=${2:-circle}
SPEED=${3:-1.0}
RADIUS=${4:-3.0}
ALT=${5:-3.0}
DUR=${6:-25}
FLIGHT_TIMEOUT=$((DUR + 35))

source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash

VINS_WS=/root/catkin_ws/src
SIM_LOG=/tmp/sim_${TRIAL}.log
MAV_LOG=/tmp/mavros_${TRIAL}.log
FT_LOG=/tmp/ft_${TRIAL}.log
VINS_LOG=/tmp/vins_${TRIAL}.log
FLY_LOG=/tmp/flight_${TRIAL}.log
REC_LOG=/tmp/rec_${TRIAL}.log
CSV=/tmp/trial_${TRIAL}_path.csv

kill_chain() {
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
  pkill -9 -f 'path_record[e]r' 2>/dev/null
  sleep 2
}

wait_hz() {
  local topic=$1 min=$2 maxt=$3
  local i r got
  for ((i = 0; i < maxt; i++)); do
    r=$(timeout 7 rostopic hz "$topic" 2>/dev/null | awk '/average rate/ {print $3; exit}')
    if [ -n "$r" ]; then
      got=$(awk -v v="$r" -v m="$min" 'BEGIN{print (v+0>=m)?1:0}')
      if [ "$got" = "1" ]; then
        echo "READY $topic rate=$r"
        return 0
      fi
    fi
    sleep 1
  done
  echo "FAIL_WAIT $topic"
  return 1
}

echo "=== TRIAL $TRIAL traj=$TRAJ speed=$SPEED radius=$RADIUS alt=$ALT dur=$DUR ==="
kill_chain

# --- roscore ---
if ! timeout 4 rostopic list >/dev/null 2>&1; then
  nohup roscore >/tmp/roscore_${TRIAL}.log 2>&1 &
  sleep 6
fi
timeout 3 rostopic list >/dev/null 2>&1 || { echo "RESULT FAIL roscore"; exit 1; }

# --- sim ---
nohup bash /root/sim_launch.sh >"$SIM_LOG" 2>&1 &
wait_hz /iris_fpv_cam/usb_cam/image_raw 10 45 || { echo "RESULT FAIL sim_camera"; exit 1; }

# --- mavros ---
nohup roslaunch /root/catkin_ws/src/mavros/mavros/launch/px4.launch \
  fcu_url:=udp://:14540@127.0.0.1:14557 >"$MAV_LOG" 2>&1 &
wait_hz /mavros/imu/data_raw 40 35 || { echo "RESULT FAIL mavros_imu"; exit 1; }

# --- vins stack ---
nohup rosrun feature_tracker feature_tracker \
  _config_file:=$VINS_WS/vins_research/config/sim_config.yaml \
  _vins_folder:=$VINS_WS/VINS-Mono >"$FT_LOG" 2>&1 &
nohup rosrun vins_estimator vins_estimator \
  _config_file:=$VINS_WS/vins_research/config/sim_config.yaml \
  _vins_folder:=$VINS_WS/VINS-Mono >"$VINS_LOG" 2>&1 &
sleep 10

# --- recorder ---
RECORD_DUR=$(awk -v d="$DUR" 'BEGIN{printf "%.0f", d+15}')
nohup python3 -u /tmp/path_recorder.py --duration "$RECORD_DUR" --out "$CSV" >"$REC_LOG" 2>&1 &
sleep 2

# --- raw-mavlink arm + offboard ---
ARM_LOG=/tmp/arm_${TRIAL}.log
timeout 60 python3 -u /tmp/mavlink_arm.py >"$ARM_LOG" 2>&1
ARM_RC=$?
echo "ARM_TAIL: $(tail -2 "$ARM_LOG" 2>/dev/null | tr '\n' '|')"

# --- flight (pre-armed) ---
timeout "$FLIGHT_TIMEOUT" python3 -u /tmp/waypoint_flight.py --pre-armed \
  --trajectory "$TRAJ" --speed "$SPEED" --radius "$RADIUS" \
  --altitude "$ALT" --duration "$DUR" >"$FLY_LOG" 2>&1
FLY_RC=$?
sleep 4

# --- summary ---
N_VINS=$(grep -cE ',[0-9-]' "$CSV" 2>/dev/null)
N_GT=$(grep -cE '^[0-9.]+,[^,]*,[^,]*,[^,]*,[0-9]+,-?[0-9]' "$CSV" 2>/dev/null)
VINS_INIT=$(grep -ciE 'initialization|success|ros_estimator' "$VINS_LOG")
POLL_ERR=$(grep -c 'poll timeout' "$SIM_LOG")
LAST_FLY=$(tail -1 "$FLY_LOG" 2>/dev/null | cut -c1-80)
echo "FLIGHT_LOG1: $(head -1 "$FLY_LOG" 2>/dev/null)"
echo "FLIGHT_LOG_LAST: $LAST_FLY"
echo "VINS_LOG_TAIL: $(tail -2 "$VINS_LOG" 2>/dev/null | cut -c1-90 | tr '\n' '|')"
echo "CSV_RANGE: $(head -2 "$CSV" 2>/dev/null | tail -1 | cut -c1-80)"
kill_chain
echo "RESULT trial=$TRIAL fly_rc=$FLY_RC csv_rows=$N_VINS gt_rows=$N_GT vins_init_markers=$VINS_INIT poll_err=$POLL_ERR"
exit 0