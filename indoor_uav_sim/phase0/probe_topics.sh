#!/usr/bin/env bash
# list uORB topics via px4 console + ekf2 status
set -u
RES=/tmp/probe4.log
> "$RES"
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
mkdir -p "$HOME/bin"
install -m 755 /mnt/d/Things/indoor_uav_sim/phase0/bin/gz "$HOME/bin/gz"
export PATH="$HOME/bin:$PATH"
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2
cd "$HOME/PX4-Autopilot/build/px4_sitl_default/src/modules/simulation/gz_bridge" || exit 1
PX4_BIN="$HOME/PX4-Autopilot/build/px4_sitl_default/bin/px4"

CMDS="list_topics
ekf2 status
"
printf '%s' "$CMDS" | timeout 60 "$PX4_BIN" > "$RES" 2>&1
echo "exit=$?" >> "$RES"

echo "=== list_topics output ===" >> "$RES"
awk '/list_topics/,/ekf2 status/' "$RES" | grep -aE 'sensor|ekf|vehicle_|estimator' >> "$RES"
echo "=== ekf2 status block ===" >> "$RES"
awk '/ekf2 status/,/PX4 Exiting/' "$RES" | head -40 >> "$RES"
echo "=== any errors ===" >> "$RES"
grep -aE 'ERROR|canot|cannot|failed' "$RES" | grep -av 'pxh> ' | head -20 >> "$RES"