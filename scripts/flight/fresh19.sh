#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
if ! pgrep -x roscore >/dev/null 2>&1; then
  nohup roscore >/tmp/roscore.log 2>&1 &
  sleep 5
fi
export HEADLESS=1 NO_PXH=1 PX4_SIM_MODEL=gazebo-classic_iris
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
export DISPLAY=:0
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null; sleep 2
# gzserver w/ ros plugins
timeout 60 gzserver --verbose \
  /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world \
  -s libgazebo_ros_api_plugin.so -s libgazebo_ros_paths_plugin.so \
  >/tmp/fresh19_gz.log 2>&1 &
GZPID=$!
sleep 10
echo "=== spawn model ==="
timeout 20 gz model --verbose --spawn-file=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf --model-name=iris_fpv_cam -x 1.01 -y 0.98 -z 0.83 2>&1 | grep -c Err
sleep 4
echo "=== mag before px4 ==="
timeout 5 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -2
echo "=== start px4 ==="
cd /root/PX4-Autopilot/build/px4_sitl_default/rootfs
timeout 45 /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 -d /root/PX4-Autopilot/build/px4_sitl_default/etc >/tmp/fresh19_px4.log 2>&1 &
PX4_PID=$!
sleep 15
echo "=== px4 log tail ==="
grep -aE 'mavlink.*on|log|INFO' /tmp/fresh19_px4.log | head -5
echo "=== mag after px4 ==="
timeout 6 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -2
echo "=== MAGDBG after px4 ==="
grep -a 'MAGDBG' /tmp/fresh19_gz.log | tail -6
echo "=== gz errors ==="
grep -aE 'Err|Failed' /tmp/fresh19_gz.log | grep -v 'display\|ros_api\|RosApi\|XmlRpc\|write error\|couldn.t\|write api' | head -5
kill -9 $GZPID $PX4_PID 2>/dev/null; sleep 1
echo DONE