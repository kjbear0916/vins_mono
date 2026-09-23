#!/bin/bash
# Blocker is NOT px4: it's gzserver being <defunct> so iris_fpv_cam camera
# plugin never registers /cam0/image_raw + /imu0. This run CLEANS AROUND
# gazebo (rm defunct, fresh gzserver w/ camera world) WITHOUT killing px4,
# then waits up to 200s (cz cold-start is slow), then audits + records 45s.
L=/tmp/gz200.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

echo "==PRE_GZSERVER==" >> "$L"
pgrep -ax gzserver >> "$L" 2>&1 || echo NONE >> "$L"

# remove defunct gzserver entries WITHOUT touching px4
for g in $(pgrep -x gzserver); do
  kill -0 "$g" 2>/dev/null && continue
  kill -9 "$g" 2>/dev/null
done
pkill -x gzserver 2>/dev/null; sleep 3
echo "==POST_CLEAN_PX4_ALIVE=" >> "$L"
pgrep -x px4 >> "$L" 2>&1 && echo "  PX4_KEPT_ALIVE=YES" >> "$L"

# gazebo world WITH the camera (from the SAME sim world that wire proved)
cd /root/PX4-Autopilot
W=$(find / -name "iris_fpv_cam*.sdf" 2>/dev/null | head -1)
echo "==CAM_MODEL_SDF=$W==" >> "$L"
if [ -n "$W" ]; then
  P=$(dirname "$W")
  WORLD=$(find /root/PX4-Autopilot/Tools -name "*.world" 2>/dev/null | grep -iE 'iris|fpv|cam' | head -1)
  echo "==WORLD=$WORLD==" >> "$L"
  WORLD=${WORLD:-/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/iris.world}
  DP=$(dirname "$P")
  export GAZEBO_MODEL_PATH="$P:$DP"
  export GAZEBO_RESOURCE_PATH=$(dirname "$WORLD")
  export DISPLAY=:99
  nohup gzserver "$WORLD" --verbose > /tmp/gz200_gz.log 2>&1 &
  echo "==GZSERVER_PID=$!==" >> "$L"
else
  echo "==NO_CAM_SDF__FALLBACK_STOCK==" >> "$L"
  nohup gzserver /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/iris.world --verbose > /tmp/gz200_gz.log 2>&1 &
  echo "==STOCK_GZ_PID=$!==" >> "$L"
fi

# iris.world spawns iris_fpv_cam? if not, spawn the model plugin now
# (independent of px4; just so camera topics exist for the bag)
sleep 4
timeout 30 gz model --spawn-model="$W" -m iris_fpv_cam -x 0 -y 0 -z 0.28 > /tmp/gz200_spawn.log 2>&1 || true

echo "==WAIT_GZ_AND_CAM_TOPIC_UP_TO_180s==" >> "$L"
GZUP=0
for i in $(seq 1 60); do
  if gz model --query-models 2>/dev/null | grep -qi iris; then GZUP=1; echo "  MODELS_AT_$((i*3))s" >> "$L"; break; fi
  sleep 3
done
sleep 10

echo "==TOPIC_AUDIT==" >> "$L"
for pair in "/cam0/image_raw:$(timeout 12 rostopic type /cam0/image_raw 2>&1)" "/imu0:$(timeout 12 rostopic type /imu0 2>&1)"; do
  echo "  $pair" >> "$L" 2>&1
done

B=/root/selfeuroc/gz_$(date -u +%H%M%S).bag; mkdir -p /root/selfeuroc
T1=$(timeout 12 rostopic type /cam0/image_raw 2>&1)
T2=$(timeout 12 rostopic type /imu0 2>&1)
if [ -n "$T1" ] && [ -n "$T2" ]; then
  echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
  timeout 70 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 45 > /tmp/gz200_rec.log 2>&1
  echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
  ls -la "$B" >> "$L" 2>&1
  echo "==AUDIT==" >> "$L"
  timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -10 >> "$L" 2>&1
else
  echo "==CAM0_OR_IMU0_MISSING__BAG_SKIPPED==" >> "$L"
  timeout 30 gz stats 2>&1 | head -5 >> "$L" 2>&1
fi
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
