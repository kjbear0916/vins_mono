#!/usr/bin/env bash
# PX4 SITL + Gazebo 啟動器 (沿用 indoor_uav_sim/phase0/run_takeoff_test.sh 已驗證流程,
# 但編譯在影像建置完成, 這裡只做「啟動＋有界等待＋tail」)。
set -u

PX4_ROOT=/root/PX4-Autopilot
RES=/tmp/phase0_result.log
LOG=/tmp/sitl.log
echo "=== entrypoint_sitl start $(date +%T) ===" >> "$RES"

export PX4_SIM_MODEL=${PX4_SIM_MODEL:-building_x500}
export PX4_GZ_WORLD=${PX4_GZ_WORLD:-building}
export PX4_HOME_LAT=${PX4_HOME_LAT:-25.0}
export PX4_HOME_LON=${PX4_HOME_LON:--80.0}
export PX4_HOME_ALT=${PX4_HOME_ALT:-0.0}
export PX4_SIMULATOR=gz
export GZ_SIM_RESOURCE_PATH="$PX4_ROOT/Tools/simulation/gz/models:/root/disaster_drone_ws/src/drone_bringup/worlds:/root/disaster_drone_ws/src/drone_bringup/models"

pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2

cd "$PX4_ROOT" || { echo "FATAL: $PX4_ROOT missing" >> "$RES"; exit 1; }
echo "launching make px4_sitl gz_${PX4_SIM_MODEL} (world=${PX4_GZ_WORLD})" >> "$RES"
make px4_sitl "gz_${PX4_SIM_MODEL}" > "$LOG" 2>&1 &
MAKE_PID=$!

up=0
for i in $(seq 1 90); do
  sleep 3
  if pgrep -f 'bin/px4' >/dev/null 2>&1 && pgrep -f 'gz sim' >/dev/null 2>&1; then
    up=1; break
  fi
done
echo "boot wait done up=$up after $((i*3))s" >> "$RES"
if [ "$up" != 1 ]; then
  echo "FAIL: px4/gz did not come up"; echo "log tail:" >> "$RES"
  timeout 5 tail -c 3000 "$LOG" >> "$RES" 2>&1
  kill "$MAKE_PID" 2>/dev/null
fi

# 永續: 容器存活 + tail 模擬 log (Ctrl-C 由 compose 前處理)
trap 'kill "$MAKE_PID" 2>/dev/null; pkill -f "bin/px4"; pkill -f "gz sim"; exit 0' INT TERM
timeout "${SITL_TTL:-7200}" tail -f "$LOG"
exit 0