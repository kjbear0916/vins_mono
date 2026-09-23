#!/bin/bash
# px4 is ALIVE RIGHT NOW (native restart chain, full-rate window open).
# Do NOT touch it. Just: put the working companion in place -> start it ->
# record cam0+imu0 for the window -> audit. All one file, no relaunch.
L=/tmp/livebag.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
echo "==PX4_NOW==" >> "$L"
pgrep -ax px4 >> "$L" 2>&1

# put the PROVEN companion (from /tmp/library) into the static expected path
cp -f /tmp/companion.py /root/catkin_ws/src/VINS-Mono/companion4.py 2>>"$L"
cp -f /tmp/companion2.py /root/catkin_ws/src/VINS-Mono/companion5.py 2>>"$L"
ls -la /root/catkin_ws/src/VINS-Mono/companion4.py 2>&1 >> "$L"

# start companion binding 0.0.0.0:14540 immediately (do not disturb px4)
nohup python3 /tmp/companion.py > /tmp/live_cmp.log 2>&1 &
echo "==COMPANION_PID=$! ==" >> "$L"

# give it 2s to bind+HB
sleep 2

# record cam0+imu0 30s into a bag while companion keeps the link full-rate
mkdir -p /root/vinsbones
cd /root/vinsbones
B="/root/vinsbones/live_$(date -u +%H%M%S).bag"
echo "==RECORDING_BAG=$B ==" >> "$L"
timeout 40 rosbag record -q -O "$B" /cam0/image_raw /imu0 --duration 30 > /tmp/livebag_r.log 2>&1
echo "==BAG_REC_END $(date -u +%H:%M:%S)==" >> "$L"

# audit: bytes on disk + topics inside bag
echo "==BAG_BYTES==" >> "$L"
ls -la /root/vinsbones/*.bag 2>&1 >> "$L"
B_LAST=$(ls -t /root/vinsbones/*.bag 2>/dev/null | head -1)
if [ -n "$B_LAST" ]; then
  echo "==BAG_INFO_$B_LAST==" >> "$L"
  timeout 30 rosbag info "$B_LAST" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -14 >> "$L" 2>&1
fi
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
