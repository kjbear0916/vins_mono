#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4; pkill -9 -x Xvfb; sleep 1
timeout 25 gzserver --verbose /tmp/only_iris.world >/tmp/only_iris.log 2>&1 &
SLEEP 6
echo "=== log lines ==="
grep -aiE 'imu|mag|baro|motor|mavlink|load' /tmp/only_iris.log | head -10
echo "=== topics ==="
timeout 3 gz topic -l 2>/dev/null | grep -iE 'imu|mag|baro|motor|ground' | head
echo "=== IMU echo (GetName-based guess /iris/imu and /iris_mag etc) ==="
timeout 4 gz topic -e '/gazebo/default/iris/imu' 2>/dev/null | head -c 120
echo
echo "=== groundtruth echo ==="
timeout 4 gz topic -e '/gazebo/default/iris/groundtruth' 2>/dev/null | head -c 120