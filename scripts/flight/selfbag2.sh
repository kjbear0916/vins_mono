#!/bin/bash
# docker-restart-native-chain + companion-from-second-0 + 35s self-record of
# /cam0/image_raw + /imu0. One file, provable by bag bytes afterward.
L=/tmp/selfbag2.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

# 1) companion (wire-proven: 0.0.0.0:14540, HB+setpoints 5Hz, continuous)
#    relaunched from second-0 so px4 sees a live partner during boot.
if [ -f /root/catkin_ws/src/VINS-Mono/companion4.py ]; then
  nohup python3 /root/catkin_ws/src/VINS-Mono/companion4.py > /tmp/selfbag_cmp.log 2>&1 &
  echo "==COMPANION_PID=$! ==" >> "$L"
else
  echo "==NO_COMPANION4==" >> "$L"
fi

# 2) wait for px4 via the NATIVE chain (opened by docker restart; do NOT touch it)
echo "==WAIT_PX4=" >> "$L"
PX4UP=0
for i in $(seq 1 30); do
  if pgrep -x px4 >/dev/null 2>&1; then PX4UP=1; echo "  UP_AT_${i}x2s" >> "$L"; break; fi
  sleep 2
done
[ "$PX4UP" = 1 ] || { echo "PX4_NEVER_UP_NATIVE" >> "$L"; cat "$L"; exit 1; }

# a few seconds for camera plugin to start publishing
sleep 8

# 3) record 35s of cam0 + imu0 into a bag
echo "==RECORDER_START=$(date -u +%H:%M:%S)==" >> "$L"
mkdir -p /root/euroc_self
cd /root/euroc_self
timeout 45 rosbag record -q -O /root/euroc_self/self_$(date -u +%H%M%S).bag \
  /cam0/image_raw /imu0 --duration 35 > /tmp/selfbag_rec.log 2>&1
echo "==RECORDER_END=$(date -u +%H:%M:%S)==" >> "$L"

# 4) audit the bag bytes
echo "==BAG_AUDIT==" >> "$L"
B=$(ls -t /root/euroc_self/*.bag 2>/dev/null | head -1)
if [ -n "$B" ]; then
  echo "  BAG=$B size=$(stat -c%s "$B")" >> "$L"
  timeout 40 rosbag info "$B" 2>&1 | grep -iE '^ *[0-9]|duration|topics|/cam0|/imu0' | head -12 >> "$L" 2>&1
else
  echo "  NO_BAG_WRITTEN" >> "$L"
fi
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
