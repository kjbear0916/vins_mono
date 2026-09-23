#!/bin/bash
set +u
pkill -9 -f mavsdk_server; sleep 1
timeout 40 python3 /workspace/disaster_drone_ws/tools/mavsdk_udp.py > /tmp/mavsdk_udp.log 2>&1
cat /tmp/mavsdk_udp.log