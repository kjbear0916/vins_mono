#!/bin/bash
# FINAL atomic relaunch. One px4 chain (iris_fpv_cam, correct cwd), one
# tcpdump (loopback on 14540/14550), one companion bound 0.0.0.0:14540
# advertising HB + OFFBOARD from second-0, all started in the SAME exec as
# the sim so the "fresh window" and "companion speaking" are the same
# instant. No second relaunch anywhere. Log to file, no PS-visible tokens.
L=/tmp/finalone.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

# fresh clean chain: kill gazebo-era chain AND sitl_run spa-ped px4
pkill -x gzserver 2>/dev/null; pkill -x px4 2>/dev/null
pkill -f sitl_run.sh 2>/dev/null; pkill -f sitl_launch.sh 2>/dev/null
pkill -f sim_launch.sh 2>/dev/null; sleep 4

# launch from the directory that PROVED full-rate in wire60: build dir cwd,
# sitl_run.sh px4 none iris_fpv_cam empty
cd /root/PX4-Autopilot/build/px4_sitl_default 2>/dev/null || cd /root/PX4-Autopilot/build/px4_sitl_default
export DISPLAY=:99
# keep roscore alive (pid 49/63), start sim chain
nohup bash /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh \
  /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 none iris_fpv_cam empty \
  /root/PX4-Autopilot /root/PX4-Autopilot/build/px4_sitl_default \
  > /tmp/finalone_sim.log 2>&1 &
echo "==SIM_PID=$!" >> "$L"

# wait px4 slow start (up to 45s)
for i in $(seq 1 45); do
  pgrep -x px4 >/dev/null && { echo "==PX4_UP=${i}s=$(date -u +%H:%M:%S)==" >> "$L"; break; }
  sleep 1
done
pgrep -x px4 >/dev/null || { echo "==PX4_NEVER_UP==" >> "$L"; cat "$L"; exit 1; }

# now the companion and tcpdump go up at the SAME second as the fresh window
timeout 33 timeout 28 tcpdump -i any -w /tmp/final_${W}.pcap 'udp port 14540 or udp port 14550' 2>/dev/null &
echo "==TCPDUMP_PID=$!" >> "$L" &
timeout 75 python3 /tmp/companion3.py >> "$L" 2>&1

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
echo "==PCAP_SIZE=$(stat -c%s /tmp/final_${W}.pcap 2>/dev/null || echo 0)==" >> "$L"
echo "==PS_AFTER==" >> "$L"
ps -eo pid,etimes,cmd | grep -E 'gzserver|/bin/px4|tcpdump' | grep -v grep >> "$L" 2>&1
cat "$L"
