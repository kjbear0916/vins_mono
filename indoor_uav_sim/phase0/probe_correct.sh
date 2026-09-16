#!/usr/bin/env bash
# Correct topic names: sensor_accel, sensor_gyro, sensor_baro (not sensor_imu)
set -u
RES=/tmp/probe5.log
> "$RES"
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
mkdir -p "$HOME/bin"
install -m 755 /mnt/d/Things/indoor_uav_sim/phase0/bin/gz "$HOME/bin/gz"
export PATH="$HOME/bin:$PATH"
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2
cd "$HOME/PX4-Autopilot/build/px4_sitl_default/src/modules/simulation/gz_bridge" || exit 1
PX4_BIN="$HOME/PX4-Autopilot/build/px4_sitl_default/bin/px4"

CMDS="listener sensor_accel 2
listener sensor_gyro 2
listener sensor_baro 2
listener vehicle_gps_position 1
listener vehicle_local_position 1
ekf2 status
"
printf '%s' "$CMDS" | timeout 90 "$PX4_BIN" > "$RES" 2>&1
echo "exit=$?" >> "$RES"

echo "=== filtered useful ===" >> "$RES"
grep -aE '\[ekf2\]|sensor_accel|sensor_gyro|sensor_baro|vehicle_gps|vehicle_local|EKF dt' "$RES" | grep -av 'pxh> ' | head -40 >> "$RES"