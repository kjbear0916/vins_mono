#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; sleep 2
gzserver --verbose /tmp/iso_phy.world >/tmp/iso10.log 2>&1 &
GZIP=$!
sleep 8
echo "=== -z imu ==="
timeout 6 gz topic -z '/gazebo/iris/irisimu' 2>&1 | head -5
echo "=== -z pose/info ==="
timeout 6 gz topic -z '/gazebo/iso/pose/info' 2>&1 | head -5
kill -9 $GZIP 2>/dev/null
echo "DONE"