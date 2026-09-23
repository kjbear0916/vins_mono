#!/bin/bash
set +u
pkill -9 -f mavsdk_server; sleep 1
BIN=/usr/local/lib/python3.12/dist-packages/mavsdk/bin/mavsdk_server
echo "== help =="
timeout 5 $BIN --help 2>&1 | head -25
echo "== debug run =="
timeout 12 $BIN -p 50051 udpin://0.0.0.0:14540 --debug 2>&1 | head -30
echo "exit=$?"