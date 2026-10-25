#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4; pkill -9 -x Xvfb; sleep 1
WORLD=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world
timeout 30 gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_api_plugin.so \
  /root/PX4-Autopilot/build/px4_sitl_default/rootfs/gazebo/iris.world 2>&1 \
  | grep -aiE 'imu|mag|baro|mavlink|motor|Failed|Load' | head -30