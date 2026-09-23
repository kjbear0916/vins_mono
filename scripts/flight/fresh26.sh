#!/bin/bash
source /root/catkin_ws/devel/setup.bash
source /opt/ros/noetic/setup.bash
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4 2>/dev/null; pkill -9 -f sitl_run.sh 2>/dev/null; pkill -9 -f gzclient 2>/dev/null; sleep 2
if ! pgrep -x roscore >/dev/null 2>&1; then
  nohup roscore >/tmp/roscore.log 2>&1 &
  sleep 5
fi

nohup env DISPLAY=:0 HEADLESS=1 NO_PXH=1 PX4_SIM_MODEL=gazebo-classic_iris bash /root/sim_launch.sh >/tmp/fresh26_sim.log 2>&1 &
sleep 25
echo "=== px4 conn ==="
grep -aE 'Simulator connected' /tmp/fresh26_sim.log | head -2
echo "=== MAVLINKDBG counts (30s sample) ==="
before=$(grep -ac 'MAVLINKDBG' /tmp/fresh26_sim.log)
sleep 8
after=$(grep -ac 'MAVLINKDBG' /tmp/fresh26_sim.log)
echo "IMU+mag+baro called $((after-before)) times in 8s"
echo "=== ekf watch 25s ==="
timeout 25 python3 -u /tmp/ekf_watch.py 2>&1 | tail -14
echo "=== param + arm ==="
python3 -u /tmp/mavlink_arm.py 2>&1 | tail -18
echo "DONE"