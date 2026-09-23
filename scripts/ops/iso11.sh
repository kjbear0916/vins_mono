#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; sleep 2
gzserver --verbose /tmp/iso_phy.world >/tmp/iso11.log 2>&1 &
GZIP=$!
sleep 8
echo "=== [1] -z imu with -w iris ==="
timeout 4 gz topic -z -w iris '/gazebo/iris/irisimu' 2>&1 | head -3
echo "=== [2] -e imu with -d 2 (stderr kept) ==="
timeout 4 gz topic -e -d 2 '/gazebo/iris/irisimu' 2>&1 | head -c 150
echo
echo "=== [3] -i imu ==="
timeout 3 gz topic -i '/gazebo/iris/irisimu' 2>&1 | tail -8
kill -9 $GZIP 2>/dev/null
echo "DONE"