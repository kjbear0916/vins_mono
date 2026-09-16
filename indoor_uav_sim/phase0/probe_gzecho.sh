#!/usr/bin/env bash
# Determine whether the gz server actually *streams* imu/baro (vs just having the topic),
# and what uORB topics px4 exposes (list_topics).
set -u
RES=/tmp/probe2.log
> "$RES"
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
mkdir -p "$HOME/bin"
install -m 755 /mnt/d/Things/indoor_uav_sim/phase0/bin/gz "$HOME/bin/gz"
export PATH="$HOME/bin:$PATH"

pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2

cd "$HOME/PX4-Autopilot/build/px4_sitl_default/src/modules/simulation/gz_bridge" || exit 1
PX4_BIN="$HOME/PX4-Autopilot/build/px4_sitl_default/bin/px4"

# Start px4 in background, then in parallel probe gazebo topics while it runs
"$PX4_BIN" > /tmp/px4raw.log 2>&1 &
PX4_PID=$!

sleep 25

IMU=/world/default/model/x500_0/link/base_link/sensor/imu_sensor/imu
BARO=/world/default/model/x500_0/link/base_link/sensor/air_pressure_sensor/air_pressure

echo "=== gz imu echo 4s (count/bytes) ===" >> "$RES"
timeout 4 gz topic -e -t "$IMU" 2>&1 | head -3 | cat -v >> "$RES"
echo "--- imu echo byte count over 4s:" >> "$RES"
timeout 4 gz topic -e -t "$IMU" 2>/dev/null | wc -c >> "$RES"
echo "=== gz baro echo byte count over 4s:" >> "$RES"
timeout 4 gz topic -e -t "$BARO" 2>/dev/null | wc -c >> "$RES"

kill -INT $PX4_PID 2>/dev/null
sleep 3
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo "=== end ===" >> "$RES"