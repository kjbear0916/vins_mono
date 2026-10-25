#!/bin/bash
# Fresh sitl chain + tcpdump wire capture. Run INSIDE container.
set -x
cd /root
pkill -x gzserver 2>/dev/null
pkill -x px4 2>/dev/null
pkill -f "sitl_run.sh" 2>/dev/null
pkill -f "sim_launch.sh" 2>/dev/null
sleep 4
ps -eo pid,cmd | grep -E "gzserver|/bin/px4" | grep -v grep
echo "--- KILLED_CLEAN ---"
export DISPLAY=:99
export HEADLESS=1
export PX4_SIM_MODEL=iris_fpv_cam
nohup bash sim_launch.sh > /tmp/sim60.log 2>&1 &
echo "--- wait px4 boot ---"
sleep 28
ps -eo pid,etimes,cmd | grep -E "gzserver|/bin/px4" | grep -v grep
echo "--- SIM_UP capture 30s ---"
timeout 30 tcpdump -i any -nn -w /tmp/wire60.pcap "udp and (port 14540 or port 14550 or port 14580)" &
TCPID=$!
wait $TCPID
ls -l /tmp/wire60.pcap
echo "--- WIRE_DONE ---"
