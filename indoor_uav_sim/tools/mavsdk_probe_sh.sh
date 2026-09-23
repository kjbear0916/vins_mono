#!/bin/bash
set +u
timeout 25 python3 /workspace/disaster_drone_ws/tools/mavsdk_probe.py > /tmp/mavsdk_probe.log 2>&1
wc -l /tmp/mavsdk_probe.log
cat /tmp/mavsdk_probe.log