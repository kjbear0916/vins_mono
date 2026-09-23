#!/bin/bash
source /opt/ros/noetic/setup.bash
export DISPLAY=:0
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null; sleep 2
# use xvfb-run with explicit output redirect — we need its output
xvfb-run -a -s '-screen 0 1920x1080x24' timeout 35 gzserver --verbose \
  /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world \
  -s libgazebo_ros_api_plugin.so -s libgazebo_ros_paths_plugin.so \
  2>&1 | tee /tmp/fresh13_gz.log &
sleep 10
echo "=== gzserver alive? ==="
ps -eo args | grep -a 'gzserver' | grep -v grep | head -2
echo "=== spawn ==="
timeout 15 gz model --verbose --spawn-file=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf --model-name=iris_fpv_cam -x 1.01 -y 0.98 -z 0.83 2>&1 | head -5
sleep 3
echo "=== topics ==="
timeout 3 gz topic -l 2>/dev/null | grep -E 'mag|baro|imu|ground' | head
echo "=== mag hz ==="
timeout 5 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -2
echo "=== MAGDBG ==="
grep -a 'MAGDBG' /tmp/fresh13_gz.log | head -5
echo "=== errors ==="
grep -aE 'Failed|Err' /tmp/fresh13_gz.log | grep -v 'display\|render\|X window\|XmlRpc\|ros_api\|ros_paths' | head -5
echo "=== gz log size ==="
wc -l /tmp/fresh13_gz.log 2>/dev/null
echo DONE