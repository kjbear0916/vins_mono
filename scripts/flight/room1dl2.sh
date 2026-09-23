#!/bin/bash
# ONE self-contained file: launch TUM-VI room1 bag download in background
# (wget -c resumable), then poll real byte flow for ~55s. All side effects
# land in /tmp/room1dl.log via >>, never via PowerShell-visible operators.
L=/tmp/room1dl.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

mkdir -p /root/euroc
cd /root/euroc

URL="https://cvg.cit.tum.de/_media/data/datasets/visual-inertial-dataset/dataset-room1_512_16.bag"
BAG="dataset-room1_512_16.bag"

nohup wget -c -q -O "$BAG" "$URL" > /tmp/wget_room1.nohup 2>&1 &
echo "WGET_PID=$!" >> "$L"

# poll real bytes for ~55s
for i in $(seq 1 11); do
  sleep 5
  B=$(stat -c%s "$BAG" 2>/dev/null || echo 0)
  A=$(kill -0 $! 2>/dev/null && echo ALIVE || echo DONE)
  echo "POLL[$i]=$(date -u +%H:%M:%S) bytes=$B state=$A" >> "$L"
done

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
