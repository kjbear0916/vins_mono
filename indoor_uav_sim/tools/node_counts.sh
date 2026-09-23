#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
echo "== raw list with counts =="
ros2 node list 2>/dev/null | sort | uniq -c | sort -rn | head -15
echo "== python procs =="
ps aux | grep -E 'python3.*_(node|launch)' | grep -v grep | awk '{print $2, $11, $12, $13}' | head -40