#!/usr/bin/env bash
# Diag with the Garden shim active: verify gz CLI resolves, which topics exist,
# whether IMU/baro/navsat data flows, and px4 ekf2/health state.
set -u
RES=/tmp/phase0_gzdiag.log
> "$RES"
rm -f /tmp/px4gzdiag.log
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
mkdir -p "$HOME/bin"
install -m 755 /mnt/d/Things/indoor_uav_sim/phase0/bin/gz "$HOME/bin/gz"
export PATH="$HOME/bin:$PATH"

echo "=== diag start $(date +%T) ===" >> "$RES"
echo "gz resolves to: $(command -v gz)" >> "$RES"

pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2
cd "$HOME/PX4-Autopilot" || exit 1
make px4_sitl gz_x500 > /tmp/px4gzdiag.log 2>&1 &
MAKE_PID=$!
sleep 50

echo "--- proc ruby/px4 ---" >> "$RES"
ps -ef | grep -E 'ruby3.0.* gz|bin/px4|gz sim' | grep -v grep >> "$RES"

echo "--- topic list (shim CLI) ---" >> "$RES"
timeout 8 gz topic -l 2>&1 | sort | sed 's/^/  /' >> "$RES"

echo "--- IMU topic stats ---" >> "$RES"
timeout 6 gz topic -i /world/default/model/x500_0/link/base_link/sensor/imu_sensor/imu 2>&1 >> "$RES"
echo "--- baro topic stats ---" >> "$RES"
timeout 6 gz topic -i /world/default/model/x500_0/link/base_link/sensor/air_pressure_sensor/air_pressure 2>&1 >> "$RES"
echo "--- navsat topic stats ---" >> "$RES"
timeout 6 gz topic -i /world/default/model/x500_0/link/base_link/sensor/navsat_sensor/navsat 2>&1 >> "$RES"

echo "--- px4 ekf2/health lines ---" >> "$RES"
timeout 10 grep -aE '\[ekf2\]|EKF|health|Ready for takeoff|blind land|gimbal|vehicle_status' /tmp/px4gzdiag.log 2>/dev/null | grep -va pxh | head -25 >> "$RES"

kill $MAKE_PID 2>/dev/null
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo "=== diag end $(date +%T) ===" >> "$RES"