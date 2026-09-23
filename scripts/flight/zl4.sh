#!/bin/bash
# restart native window -> WAIT LONG (gazebo cold 60-120s) -> then audit with
# FULL ROSENV (this was the recurring error: exec without setup+uri=master fail).
L=/tmp/zl4.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

# give the native chain its cold start window WITHOUT touching it
sleep 120

source /opt/ros/noetic/setup.bash 2>/dev/null
grep -q 11311 /proc/1/environ 2>/dev/null; export ROS_MASTER_URI=http://localhost:11311
echo "==PX4_ALIVE=" >> "$L"; pgrep -ax px4 >> "$L" 2>&1 || echo NONE >> "$L"
echo "==GZ_ALIVE=" >> "$L"; pgrep -ax gzserver >> "$L" 2>&1 || echo NONE >> "$L"

echo "==ROSCORE_MASTER=" >> "$L"
pgrep -ax roscore >> "$L" 2>&1 || echo NONE >> "$L"
echo "==MASTER_META=" >> "$L"
timeout 10 curl -s http://localhost:11311/ 2>&1 | head -c 100 >> "$L" 2>&1; echo >> "$L"

echo "==TOPIC_AUDIT_AFTER_120s==" >> "$L"
timeout 25 rostopic list 2>&1 | grep -iE 'cam|image|imu|px4|mav' | head -24 >> "$L" 2>&1
echo "==ALL_COUNT==" >> "$L"
timeout 25 rostopic list 2>&1 | wc -l >> "$L" 2>&1

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
