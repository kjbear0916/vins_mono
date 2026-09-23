#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4; pkill -9 -x Xvfb; sleep 2
timeout 30 gzserver --verbose /tmp/only_iris.world >/tmp/only_iris3.log 2>&1 &
sleep 10
echo "=== topics (imu/mag/baro/gt) ==="
timeout 3 gz topic -l 2>/dev/null | grep -iE 'imu|mag|baro|ground'
echo "=== IMU echo (4s, 5 lines) ==="
timeout 4 gz topic -e '/gazebo/w/iris/imu' 2>/dev/null | head -c 180
echo
echo "=== errors in log ==="
grep -a 'Error\|Failed\|undefined\|Plugin' /tmp/only_iris3.log | head -10