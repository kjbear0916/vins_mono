#!/bin/bash
set +u
pkill -9 -f mavsdk_server; sleep 1
timeout 15 /usr/local/lib/python3.12/dist-packages/mavsdk/bin/mavsdk_server -p 50051 --sysid 245 --compid 190 udpin://0.0.0.0:14540 > /tmp/mavsdk_srv.log 2>&1
echo "exit=$?"
cat /tmp/mavsdk_srv.log