#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash 2>/dev/null

export ROS_DOMAIN_ID=0
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_PARTITION=default

ros2 launch drone_bringup full_system.launch.py >/tmp/full_system.log 2>&1 &
echo "launch pid $!"
sleep 20
echo "== launch log =="
tail -c 2500 /tmp/full_system.log
echo
echo "== ros2 nodes =="
ros2 node list 2>&1 | head -20
echo "== ros2 topics =="
ros2 topic list 2>&1 | head -40