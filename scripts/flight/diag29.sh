#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic

pkill -9 -x gzserver 2>/dev/null || true
pkill -9 -x px4 2>/dev/null || true
pkill -9 -f sitl_run.sh 2>/dev/null || true
pkill -9 -f sim_launch.sh 2>/dev/null || true
sleep 2

if ! pgrep -x roscore >/dev/null 2>&1; then
  nohup roscore >/tmp/roscore.log 2>&1 &
  sleep 4
fi

nohup env DISPLAY=:0 HEADLESS=1 NO_PXH=1 PX4_SIM_MODEL=gazebo-classic_iris \
  bash /root/sim_launch.sh >/tmp/fresh29_sim.log 2>&1 &
echo "sim launching..."

# Wait for PX4 connected
for i in $(seq 1 45); do
  sleep 1
  if grep -qa 'Simulator connected' /tmp/fresh29_sim.log 2>/dev/null; then
    echo "PX4 connected at t=${i}s"
    sleep 12
    break
  fi
done

echo ""
echo "=========================================="
echo "DIAG 1: PX4 process & PID"
echo "=========================================="
pgrep -a px4 | head -3
PX4PID=$(pgrep -x px4 | head -1)
echo "PX4PID=$PX4PID"

echo ""
echo "=========================================="
echo "DIAG 2: /proc/net/udp (hex port decode)"
echo "=========================================="
cat /proc/net/udp | while read line; do
  echo "$line" | awk '{
    split($2, a, ":");
    if (NR==1) { print "HEADER: local_addr local_port state"; next }
    printf "local_port=%d  state=%s\n", strtonum("0x"a[2]), $4
  }' 2>/dev/null
done

echo ""
echo "=========================================="
echo "DIAG 3: ss -ulnp (if available)"
echo "=========================================="
ss -ulnp 2>&1 | head -20 || echo "ss not available"

echo ""
echo "=========================================="
echo "DIAG 4: PX4 startup log (mavlink lines)"
echo "=========================================="
tr -d '\r' < /tmp/fresh29_sim.log | sed 's/\x1b\[[0-9;]*m//g' | grep -aiE 'mavlink|remote|partner|18570|14580|14550|14540' | head -15

echo ""
echo "=========================================="
echo "DIAG 5: MAVLINKDBG count"
echo "=========================================="
echo "callbacks: $(grep -ac 'MAVLINKDBG' /tmp/fresh29_sim.log 2>/dev/null)"

echo ""
echo "=========================================="
echo "DIAG 6: Monitor 14550 for 8s (raw)"
echo "=========================================="
timeout 8 python3 -u /tmp/raw_14550.py 2>&1

echo ""
echo "=========================================="
echo "DIAG 7: Monitor 14540 for 8s (raw)"
echo "=========================================="
timeout 8 python3 -u /tmp/raw_14540.py 2>&1

echo ""
echo "DONE DIAGS"