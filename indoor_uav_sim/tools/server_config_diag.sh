#!/bin/bash
set +u
echo "== PX4 startup scripts =="
grep -rnE 'server.config|--server-config|server_config' /opt/PX4-Autopilot/Tools/simulation/gz/ 2>/dev/null | head -15
echo
echo "== current gz sim cmdline =="
ps aux | grep 'gz sim' | grep -v grep
echo
echo "== server.config locations =="
find /opt/PX4-Autopilot -name 'server.config' 2>/dev/null
echo
echo "== startup script that spawns gz =="
grep -rnE 'gz sim|server.config' /opt/PX4-Autopilot/ROMFS/px4fmu_common/init.d-posix/rcS 2>/dev/null | head