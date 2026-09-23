#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4; sleep 2
gzserver --verbose /tmp/iso_phy.world >/tmp/iso4.log 2>&1 &
GZIP=$!
echo "gzserver pid: $GZIP"
for i in 1 2 3 4 5 6; do
  sleep 2
  if kill -0 $GZIP 2>/dev/null; then
    ST="ALIVE"
  else
    ST="DEAD"
  fi
  echo "t=$((i*2))s: $ST"
  if [ "$ST" = "DEAD" ]; then
    wait $GZIP; echo "exit_code=$?"; break
  fi
done
echo "=== imi echo (2s) ==="
timeout 2 gz topic -e '/gazebo/iris/irisimu' 2>/dev/null | head -c 120
echo
kill -9 $GZIP 2>/dev/null
echo "=== last log lines ==="
tail -6 /tmp/iso4.log | tr -d '\r' | sed 's/\x1b\[[0-9;]*m//g'