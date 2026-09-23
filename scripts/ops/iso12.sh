#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
pkill -9 -x gzserver 2>/dev/null; sleep 2
gzserver --verbose /tmp/iso_phy.world >/tmp/iso12.log 2>&1 &
GZIP=$!
sleep 8
echo "=== imu echo raw to file (3s) ==="
timeout 4 gz topic -e '/gazebo/iris/irisimu' >/tmp/imu_echo.dat 2>/tmp/imu_echo.err
echo "exit=$?"
echo "--- stdout bytes: $(wc -c < /tmp/imu_echo.dat) ---"
head -c 160 /tmp/imu_echo.dat
echo
echo "--- stderr ---"
head -c 200 /tmp/imu_echo.err
kill -9 $GZIP 2>/dev/null
echo "DONE"