#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4; sleep 2
timeout 22 gzserver --verbose /tmp/iso_phy.world >/tmp/iso2.log 2>&1 &
sleep 12
echo "=== all topics ==="
timeout 3 gz topic -l 2>/dev/null | grep -vE 'user_cmd|pose/local|world_stats|/physics|/scene|/visual|/factory|/sensor|/joint|/model/|/response|/request|/diag|/playback|/ro[a-z]|factory/light|light/modify|world_wind|performance|motor_failure|server/control|world/modify|/log/' | head -20
echo "=== echo irisimu (imu) ==="
timeout 4 gz topic -e '/gazebo/iris/irisimu' 2>/dev/null | head -c 150
echo
echo "=== echo irismag ==="
timeout 4 gz topic -e '/gazebo/iris/irismag' 2>/dev/null | head -c 150
echo
echo "=== echo groundtruth ==="
timeout 4 gz topic -e '/gazebo/iris/iris/groundtruth' 2>/dev/null | head -c 150
echo
echo "=== physics topic echo (stepping?) ==="
timeout 4 gz topic -e '/gazebo/iso/physics' 2>/dev/null | head -c 200