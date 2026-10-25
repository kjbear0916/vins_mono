#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; sleep 2
timeout 18 gzserver --verbose /tmp/iso_phy.world >/tmp/iso3.log 2>&1 &
sleep 9
echo "=== gz stats -w iso (2s) ==="
timeout 2 gz stats -w iso 2>&1 | head -c 300
echo
echo "=== imu echo (2s) ==="
timeout 2 gz topic -e '/gazebo/iris/irisimu' 2>/dev/null | head -c 120