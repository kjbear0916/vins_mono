#!/bin/bash
set +u
pkill -9 -f mavsdk_server; sleep 1
timeout 20 python3 /workspace/disaster_drone_ws/tools/mavsdk_status.py > /tmp/mavsdk_status.log 2>&1
cat /tmp/mavsdk_status.log