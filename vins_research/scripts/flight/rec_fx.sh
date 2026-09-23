#!/bin/bash
L=/tmp/rec_fx.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null

echo "==PX4_CHECK==" >> "$L"
pgrep -ax px4 >> "$L" 2>&1 || true

echo "==COMPANION_ALIVE==" >> "$L"
pgrep -af 'companion_ready|companion.py' >> "$L" 2>&1 || true

echo "==SOURCES==" >> "$L"
# companion_ready binds 0.0.0.0:14540 -> proves server was first even if HB idle
timeout 12 bash -c 'exec 3<>/dev/tcp/127.0.0.1/14540; timeout 10 dd bs=1 count=8 <&3 2>/dev/null | xxd | head -2' > /tmp/hbsrc_probe.dat 2>&1
echo "--HB_PROBE_BYTES=$(stat -c%s /tmp/hbsrc_probe.dat 2>/dev/null||echo 0)--" >> "$L"

# if px4 up -> record cam0+imu0 22s into ONE fixed bag name
P=$(pgrep -x px4 | head -1)
if [ -n "$P" ]; then
  echo "==PX4_PID=$P==" >> "$L"
  mkdir -p /root/vinsbones
  B=/root/vinsbones/atomic_fixed.bag; rm -f "$B"
  echo "==REC_START=$(date -u +%H:%M:%S)==" >> "$L"
  timeout 45 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 20 > /tmp/rec_fx.log 2>&1 &
  R=$!
  # also, while truly acceptable in-stream, let the bag 20s breath
  wait $R
  echo "==REC_END=$(date -u +%H:%M:%S)==" >> "$L"
  ls -la "$B" 2>&1 >> "$L"
  echo "==BAG_INFO==" >> "$L"
  timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages' | head -6 >> "$L" 2>&1
  timeout 40 rosbag info "$B" 2>&1 | grep -iE '/cam0|/imu0|topics' | head -8 >> "$L" 2>&1
else
  echo "==PX4_STILL_DOWN==" >> "$L"
fi
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
