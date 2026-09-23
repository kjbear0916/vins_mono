#!/bin/bash
set +u
timeout 40 python3 /workspace/disaster_drone_ws/tools/mavsdk_probe2.py > /tmp/mavsdk_probe2.log 2>&1
echo "exit=$?"
cat /tmp/mavsdk_probe2.log | tail -30
echo "== mavsdk_server procs =="
ps aux | grep mavsdk_server | grep -v grep