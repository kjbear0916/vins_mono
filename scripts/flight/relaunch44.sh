#!/bin/bash
# Fresh relaunch of the PX4 SITL chain and capture the actual wire packets.
set -x
cd /root
pkill -x gzserver 2>/dev/null
pkill -x px4 2>/dev/null
pkill -f "sitl_run.sh" 2>/dev/null
pkill -f "sim_launch.sh" 2>/dev/null
sleep 4
ps -eo pid,cmd | grep -E "gzserver|/bin/px4|sitl_run|sim_launch" | grep -v grep
echo "--- relaunch ---"
export DISPLAY=:99
export HEADLESS=1
export NO_PXH=1
export PX4_SIM_MODEL=iris_fpv_cam
nohup bash sim_launch.sh > /tmp/sim44.log 2>&1 &
echo "--- wait for px4 boot ---"
sleep 25
ps -eo pid,cmd | grep -E "gzserver|/bin/px4" | grep -v grep
echo "--- boot done; capture 25s ---"
timeout 25 tcpdump -i any -nn -w /tmp/wire44.pcap "udp and (port 14540 or port 14550 or port 14580)" 2>/tmp/tcpdump44.err
echo "--- pcap bytes ---"
ls -l /tmp/wire44.pcap
echo "--- parse ---"
cp /tmp/pcap_probe.py /tmp/pcap_probe44.py
sed -i 's/path = ".*"/path = "\/tmp\/wire44.pcap"/' /tmp/pcap_probe44.py
python3 /tmp/pcap_probe44.py
