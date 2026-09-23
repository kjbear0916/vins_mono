#!/bin/bash
# ONE file: docker restart -> WAIT native px4 full-rate -> immediately record
# cam0+imu0 into a bag + companion keeps link alive from second 0.
# The ONLY state that has EVER produced full-rate is restart-fresh xthe native
# chain; we capture THAT window and only that window.
L=/tmp/rec_audit.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

# Wait for px4 to reach the native full-rate state
for i in $(seq 1 120); do
  if pgrep -x px4 >/dev/null; then
    echo "==PX4_UP_AT=${i}x1s" >> "$L"
    break
  fi
  sleep 1
done
pgrep -x px4 >/dev/null || { echo "PX4_DID_NOT_UP" >> "$L"; cat "$L"; exit 1; }

# Let the full-rate window establish
sleep 10

echo "==ROSSETUP==" >> "$L"
# find how this cm runs ros (native container started via sim_launch.sh chain)
for s in /opt/ros/noetic/setup.bash /opt/ros/melodic/setup.bash; do
  [ -f "$s" ] && { source "$s"; echo "SRC=$s" >> "$L"; break; }
done

echo "==TOPIC_PRESENCE==" >> "$L"
timeout 25 rostopic list 2>&1 | grep -iE 'cam0|image|imu0|imu|opt_flow' | head -12 >> "$L" 2>&1
timeout 25 rostopic list 2>&1 | wc -l >> "$L" 2>&1

# Record cam0+imu0 (and mavgps for later GT) into a REAL bag for 30s
BAG=/root/vinsbags/rec1_$(date -u +%H%M%S).bag
mkdir -p /root/vinsbags
echo "==RECORD30_BAG=$BAG" >> "$L"

# companion4 keeps px4 armed/full-rate; run record+companion start at once
timeout 40 rostopic echo -n1 /imu0 >/dev/null 2>&1 &
echo "==IMU_SAMPLE_BYTES=$(timeout 20 bash -c 't0=$(date +%s); b=0; timeout 15 rostopic echo /imu0 2>/dev/null | head -c0 & while [ $(( $(date +%s) - t0 )) -lt 8 ]; do b=$(stat -c%s /tmp/imu.part 2>/dev/null || echo 0); done; echo $b')" >> "$L" 2>&1

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
