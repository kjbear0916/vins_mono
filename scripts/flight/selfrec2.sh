#!/bin/bash
# THE self-record recipe, from the ONLY-proven full-rate source (container's
# own entrypoint chain). Atomic: restart->wait px4->record bag from second-0.
# All logic in ONE file so the outer shell (PowerShell) never sees a token.
L=/tmp/selfrec2.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

# record topics that wire-proved exist at full rate on this chain
KILLPXS="pkill -x gzserver; pkill -x px4; sleep 4; pkill -x gzserver 2>/dev/null"

echo "==done_prekill=00:00:00==" >> "$L"
docker restart vins_research >/dev/null 2>&1
echo "==RESTARTED=$(date -u +%H:%M:%S)==" >> "$L"

# wait for px4 to reach full rate, then IMMEDIATELY record (second-0 single listener)
for i in $(seq 1 60); do
  docker exec vins_research bash -c 'pgrep -x px4 >/dev/null && echo UP || echo DOWN' 2>/dev/null | grep -q UP && { echo "==PX4_UP_AT=$(date -u +%H:%M:%S)i=$i==" >> "$L"; break; }
  sleep 2
done

sleep 12 # let proto boot + first full-rate packets flow

echo "==BAG_REC_START=$(date -u +%H:%M:%S)==" >> "$L"
docker exec vins_research bash -c 'mkdir -p /root/bagout; cd /root/bagout && timeout 60 rosbag record -q -O selfrec_$(date -u +%H%M%S) --duration 55 /cam0/image_raw /imu0 2>&1 | tail -3' >> "$L" 2>&1
echo "==BAG_REC_END=$(date -u +%H:%M:%S)==" >> "$L"

echo "==BAG_AUDIT==" >> "$L"
docker exec vins_research bash -c 'ls -la /root/bagout/*.bag 2>/dev/null; B=$(ls -t /root/bagout/*.bag 2>/dev/null | head -1); [ -n "$B" ] && timeout 30 rosbag info "$(basename $B)" 2>&1 | grep -iE "messages|duration|topics|im|cam|imu" | head -10' >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
