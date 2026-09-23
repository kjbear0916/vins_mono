#!/bin/bash
set +u
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
timeout 4 gz topic -e -t /world/three_floor_building/model/x500_0/link/base_link/sensor/imu_sensor/imu -n 3 > /tmp/imu_echo.log 2>&1
echo "lines: $(wc -l < /tmp/imu_echo.log)"
head -c 800 /tmp/imu_echo.log
echo
echo "== baro =="
timeout 4 gz topic -e -t /world/three_floor_building/model/x500_0/link/base_link/sensor/air_pressure_sensor/air_pressure -n 3 > /tmp/baro_echo.log 2>&1
echo "lines: $(wc -l < /tmp/baro_echo.log)"
head -c 400 /tmp/baro_echo.log
echo
echo "== current px4 proc & its gz env =="
P=$(pgrep -f 'bin/px4$' | head -1)
echo "px4 pid $P"
tr '\0' '\n' < /proc/$P/environ | grep -E '^GZ_'