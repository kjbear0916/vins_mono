#!/bin/bash
source /root/catkin_ws/devel/setup.bash
source /opt/ros/noetic/setup.bash
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4 2>/dev/null; pkill -9 -f sitl_run.sh 2>/dev/null; sleep 2
if ! pgrep -x roscore >/dev/null 2>&1; then
  nohup roscore >/tmp/roscore.log 2>&1 &
  sleep 5
fi

# full chain with DISPLAY=:0 (no xvfb) so SimTime advances
nohup env DISPLAY=:0 HEADLESS=1 NO_PXH=1 PX4_SIM_MODEL=gazebo-classic_iris bash /root/sim_launch.sh >/tmp/fresh25_sim.log 2>&1 &
sleep 30
echo "=== px4 conn ==="
grep -aE 'Simulator connected|Waiting for simulator' /tmp/fresh25_sim.log | head -3
echo "=== topics hz ==="
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
for t in '/gazebo/default/iris_fpv_cam/imu' '/gazebo/default/iris_fpv_cam/mag' '/gazebo/default/iris_fpv_cam/baro' '/gazebo/default/iris_fpv_cam/groundtruth'; do
  h=$(timeout 5 gz topic -z "$t" 2>&1 | head -1)
  echo "$t -> $h"
done
echo "=== param + arm ==="
python3 -u /tmp/mavlink_arm.py 2>&1 | tail -20
echo "DONE"