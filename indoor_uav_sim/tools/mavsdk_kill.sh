#!/bin/bash
set +u
pkill -9 -f mavsdk_server
sleep 2
echo "== remaining =="
ps aux | grep mavsdk_server | grep -v grep | wc -l
timeout 40 python3 /workspace/disaster_drone_ws/tools/mavsdk_probe2.py > /tmp/mavsdk_probe3.log 2>&1
echo "exit=$?"
tail -15 /tmp/mavsdk_probe3.log