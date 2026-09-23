#!/bin/bash
set +u
pkill -9 -f px4
pkill -9 -f "gz sim"
pkill -9 -f "make px4"
pkill -9 -f mavsdk_server
pkill -9 -f run.py
sleep 3
truncate -s 0 /tmp/px4_sitl.log 2>/dev/null
df -h / | tail -1
ps aux | grep -E 'px4|gz sim|mavsdk' | grep -v grep | wc -l