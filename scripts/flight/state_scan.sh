#!/bin/bash
L=/tmp/state_scan.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
echo "==COMPANIONS==" >> "$L"
ls -la /root/catkin_ws/src/VINS-Mono/companion*.py /root/catkin_ws/src/VINS-Mono/companion_*.py /tmp/companion*.py 2>&1 >> "$L"
echo "==BAGS==" >> "$L"
ls -la /root/euroc_self/ 2>&1 >> "$L"
ls -la /root/bagout/ 2>&1 >> "$L"
echo "==PX4_ALIVE==" >> "$L"
pgrep -ax px4 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
