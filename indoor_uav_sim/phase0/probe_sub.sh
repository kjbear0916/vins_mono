#!/usr/bin/env bash
# probe_sub.rs h — does PX4 receive IMU msgs? who owns the IMU subscriber? lockstep?
set -u
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
LOG=/tmp/px4gz_probe.log

mkdir -p "$HOME/bin"
install -m 755 /mnt/d/Things/indoor_uav_sim/phase0/bin/gz "$HOME/bin/gz"
export PATH="$HOME/bin:$PATH"

pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2
cd "$HOME/PX4-Autopilot" || exit 1
make px4_sitl gz_x500 > "$LOG" 2>&1 &
MAKE_PID=$!

up=0
for i in $(seq 1 40); do
  sleep 3
  if pgrep -f 'bin/px4' >/dev/null 2>&1 && pgrep -f 'gz sim' >/dev/null 2>&1; then up=1; break; fi
done
echo "boot up=$up after $((i*3))s"
[ "$up" != 1 ] && { echo FAIL; tail -c 2000 "$LOG"; exit 1; }

echo "sleeping 60s for settle"; sleep 60

PX4PID=$(pgrep -f 'bin/px4' | head -1)
GZPID=$(pgrep -f 'gz sim' | head -1)
echo "px4 pid=$PX4PID gz pid=$GZPID"

IMU=/world/default/model/x500_0/link/base_link/sensor/imu_sensor/imu

echo "=== [A] who listens on the subscriber ports reported by gz topic -i ==="
gz topic -i -t "$IMU" 2>&1 | head -20
echo "--- px4 listening tcp endpoints (pid $PX4PID):"
timeout 5 ss -tnp 2>/dev/null | grep -E "pid=$PX4PID|px4" | head -20
echo "--- gz sim listening tcp endpoints (pid $GZPID):"
timeout 5 ss -tnp 2>/dev/null | grep -E "pid=$GZPID|gz sim" | head -20

echo "=== [B] uORB listener sensor_accel 8s ==="
timeout 10 /home/bear/PX4-Autopilot/build/px4_sitl_default/bin/px4 listener sensor_accel -n 0 -t 8 2>&1 | grep -av '^pxh' | head -20
echo "accel_listen_rc=$?"

echo "=== [C] deliverability: does a fresh gz topic -e see IMU? (3s) ==="
timeout 6 gz topic -e -t "$IMU" -n 3 2>&1 | grep -av '^$' | head -8

echo "=== [D] clock topic rate (gz-bridge lockstep / free-running sim) ==="
timeout 8 gz topic -i -t /world/default 2>&1 | head -6
timeout 6 gz topic -e -t /world/default 2>&1 | head -5

echo "=== [E] vehicle_global_position groundtruth + sensor_gyro ==="
timeout 6 /home/bear/PX4-Autopilot/build/px4_sitl_default/bin/px4 listener vehicle_global_position -n 1 -t 5 2>&1 | grep -av '^pxh' | head -8
timeout 8 /home/bear/PX4-Autopilot/build/px4_sitl_default/bin/px4 listener sensor_gyro -n 0 -t 6 2>&1 | grep -av '^pxh' | head -8

echo "=== done ==="
kill $MAKE_PID 2>/dev/null
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo cleaned