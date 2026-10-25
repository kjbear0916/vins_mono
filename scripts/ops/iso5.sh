#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; sleep 2
gzserver --verbose /tmp/iso_phy.world >/tmp/iso5.log 2>&1 &
GZIP=$!
sleep 8
echo "=== long pose/info (8s parallel) ==="
timeout 8 gz topic -e '/gazebo/iso/pose/info' 2>&1 | head -c 200 &
P1=$!
echo "=== world_control query ==="
timeout 3 gz topic -e '/gazebo/iso/world_control' 2>&1 | head -c 120 &
P2=$!
wait $P1 $P2 2>/dev/null
echo
echo "=== world_stats via physics topic? ==="
timeout 4 gz topic -e '/gazebo/iso/world_stats' 2>&1 | head -c 160
echo
kill -9 $GZIP
echo "DONE"