#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export HEADLESS=1
export NO_PXH=1
export PX4_SIM_MODEL=gazebo-classic_iris
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
export GAZEBO_MASTER_URI=http://127.0.0.1:11345
export PX4_SITL_WORLD=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world
# Start gzserver directly with output capture
xvfb-run -a -s '-screen 0 1920x1080x24' timeout 80 gzserver --verbose \
  /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world \
  -s libgazebo_ros_api_plugin.so -s libgazebo_ros_paths_plugin.so \
  >/tmp/fresh15_gz.log 2>&1 &
GZPID=$!
echo "gzserver PID=$GZPID"
sleep 10

# spawn model
timeout 20 gz model --verbose --spawn-file=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf --model-name=iris_fpv_cam -x 1.01 -y 0.98 -z 0.83 2>&1 | head -10
sleep 5
echo "=== gzserver alive ==="
ps -p $GZPID -o pid,stat,args 2>/dev/null | head -3
echo "=== gzserver topics ==="
timeout 5 gz topic -l 2>/dev/null | grep -E 'mag|baro|imu|ground' | head
echo "=== mag hz ==="
timeout 8 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -3

echo "=== start PX4 (TCP 4560) ==="
cd /root/PX4-Autopilot/build/px4_sitl_default/rootfs
timeout 60 /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 -d /root/PX4-Autopilot/build/px4_sitl_default/etc >/tmp/fresh15_px4.log 2>&1 &
PX4_PID=$!
sleep 20
echo "=== px4 log ==="
grep -a 'poll timeout\|INFO.*param\|PARAM' /tmp/fresh15_px4.log | head -10
echo "=== mag hz after px4 ==="
timeout 8 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -3
echo "=== baro hz ==="
timeout 8 gz topic -z '/gazebo/default/iris_fpv_cam/baro' 2>&1 | head -3
echo "=== MAGDBG ==="
grep -a 'MAGDBG' /tmp/fresh15_gz.log | head -10
echo "=== gz errors ==="
grep -aE 'Err|Failed|error' /tmp/fresh15_gz.log | grep -v 'display\|X window\|XmlRpc\|ros_api\|ros_paths\|xmlrpc\|Cannot' | head -5
kill -9 $GZPID $PX4_PID 2>/dev/null
echo DONE