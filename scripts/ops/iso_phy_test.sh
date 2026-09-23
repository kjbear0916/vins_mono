#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4; sleep 2
timeout 25 gzserver --verbose /tmp/iso_phy.world >/tmp/iso_phy.log 2>&1 &
sleep 12
echo "=== topic list (iris) ==="
timeout 3 gz topic -l 2>/dev/null | grep -i 'iris' | head
echo "=== groundtruth echo ==="
timeout 3 gz topic -e '/gazebo/iso/iris/groundtruth' 2>/dev/null | head -c 120
echo
echo "=== imu echo ==="
timeout 3 gz topic -e '/gazebo/iso/iris/imu' 2>/dev/null | head -c 120
echo
echo "=== plugin load lines ==="
grep -aE 'Failed to load|Failed to resolve|loaded|Loaded|RegisterPlugin|gazebo_[a-z_]*_plugin|Err' /tmp/iso_phy.log | head -12