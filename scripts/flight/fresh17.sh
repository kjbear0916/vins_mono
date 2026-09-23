#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
export DISPLAY=:0
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null; sleep 2
# test: ros plugins but no xvfb, no px4
timeout 50 gzserver --verbose \
  /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world \
  -s libgazebo_ros_api_plugin.so -s libgazebo_ros_paths_plugin.so \
  >/tmp/fresh17_gz.log 2>&1 &
GZPID=$!
sleep 10
echo "=== gzserver alive ==="
ps -p $GZPID -o pid,stat,args 2>/dev/null | head -3
echo "=== spawn ==="
timeout 20 gz model --verbose --spawn-file=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf --model-name=iris_fpv_cam -x 1.01 -y 0.98 -z 0.83 2>&1 | head -8
sleep 5
echo "=== mag hz ==="
timeout 8 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -3
echo "=== MAGDBG ==="
grep -a 'MAGDBG' /tmp/fresh17_gz.log | head -6
echo "=== last 5 lines ==="
grep -a 'MAGDBG' /tmp/fresh17_gz.log | tail -3
kill -9 $GZPID 2>/dev/null; sleep 1
echo DONE