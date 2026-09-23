#!/bin/bash
set +u
echo "== _pose_s.c around line 54 =="
sed -n '40,70p' /opt/ros/jazzy/lib/python3.12/site-packages/geometry_msgs/msg/_pose_s.c 2>/dev/null || find / -name '_pose_s.c' -path '*geometry_msgs*' 2>/dev/null | head -2
echo
echo "== source py path =="
ls -la /opt/ros/jazzy/lib/python3.12/site-packages/geometry_msgs/msg/_pose_s* 2>/dev/null
echo "== who provides geometry in pip =="
pip list 2>/dev/null | grep -iE 'geometry|ros-|ament|rclpy' | head