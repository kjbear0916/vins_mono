#!/usr/bin/env bash
# RAW gz topic info + stats RTF, with the Garden shim, against a live PX4 launch
set -u
RES=/tmp/topicrate.log
> "$RES"
rm -f /tmp/px4gztr.log
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
mkdir -p "$HOME/bin"
install -m 755 /mnt/d/Things/indoor_uav_sim/phase0/bin/gz "$HOME/bin/gz"
export PATH="$HOME/bin:$PATH"

pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2
cd "$HOME/PX4-Autopilot" || exit 1
make px4_sitl gz_x500 > /tmp/px4gztr.log 2>&1 &
MAKE_PID=$!
sleep 50

echo "=== imu info raw ===" >> "$RES"
timeout 10 gz topic -i -t /world/default/model/x500_0/link/base_link/sensor/imu_sensor/imu >> "$RES" 2>&1
echo "=== baro info raw ===" >> "$RES"
timeout 10 gz topic -i -t /world/default/model/x500_0/link/base_link/sensor/air_pressure_sensor/air_pressure >> "$RES" 2>&1
echo "=== stats echo (2s) ===" >> "$RES"
timeout 3 gz topic -e -t /world/default/stats 2>/dev/null | head -3 >> "$RES" 2>&1

kill $MAKE_PID 2>/dev/null
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo "=== end ===" >> "$RES"