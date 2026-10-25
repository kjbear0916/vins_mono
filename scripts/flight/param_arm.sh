#!/bin/bash
source /root/catkin_ws/devel/setup.bash
source /opt/ros/noetic/setup.bash
echo "=== starting chain ==="
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null
sleep 2
nohup bash /root/sim_launch.sh >/tmp/fresh8_sim.log 2>&1 &
echo "waiting 25s for chain..."
sleep 25
echo "=== chain ready, running param + arm ==="
python3 -u /tmp/mavlink_arm.py 2>&1 | tail -40
echo "=== DONE ==="