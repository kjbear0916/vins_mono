#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
echo "=== topics with mag/baro/imu/gt ==="
timeout 3 gz topic -l 2>/dev/null | grep -iE 'mag|baro|imu|groundtruth'
for topic in '/gazebo/default/iris_fpv_cam/imu' '/gazebo/default/iris_fpv_cam/mag' '/gazebo/default/iris_fpv_cam/baro' '/gazebo/default/iris_fpv_cam/groundtruth'; do
  echo "--- -z $topic ---"
  timeout 4 gz topic -z "$topic" 2>&1 | head -1
done