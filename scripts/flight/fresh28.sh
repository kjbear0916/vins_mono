#!/bin/bash
set -e
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic

pkill -9 -x gzserver 2>/dev/null || true
pkill -9 -x px4 2>/dev/null || true
pkill -9 -f sitl_run.sh 2>/dev/null || true
pkill -9 -f sim_launch.sh 2>/dev/null || true
sleep 2

if ! pgrep -x roscore >/dev/null 2>&1; then
  nohup roscore >/tmp/roscore.log 2>&1 &
  sleep 4
fi

nohup env DISPLAY=:0 HEADLESS=1 NO_PXH=1 PX4_SIM_MODEL=gazebo-classic_iris \
  bash /root/sim_launch.sh >/tmp/fresh28_sim.log 2>&1 &
echo "sim launching..."

for i in $(seq 1 45); do
  sleep 1
  if grep -qa 'Simulator connected' /tmp/fresh28_sim.log 2>/dev/null; then
    echo "PX4 connected at t=${i}s"
    sleep 15
    break
  fi
done

echo "=== MAVLINKDBG count ==="
grep -ac 'MAVLINKDBG' /tmp/fresh28_sim.log 2>/dev/null

echo "=== gz topics ==="
for t in imu mag baro groundtruth; do
  h=$(timeout 5 gz topic -z "/gazebo/default/iris_fpv_cam/$t" 2>&1 | head -1)
  echo "  $t: $h"
done

echo "=== mavlink arm (GCS port 14550) ==="
python3 -u /tmp/mavlink_arm.py 2>&1
echo "DONE"