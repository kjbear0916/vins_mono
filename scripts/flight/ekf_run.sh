#!/bin/bash
source /root/catkin_ws/devel/setup.bash
source /opt/ros/noetic/setup.bash
rm -f /tmp/ekf_check.log
python3 -u /tmp/ekf_probe.py 2>&1 | head -60