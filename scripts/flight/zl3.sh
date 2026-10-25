#!/bin/bash
L=/tmp/zl3.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
echo "==PX4_ALIVE=" >> "$L"; pgrep -ax px4 >> "$L" 2>&1 || echo NONE >> "$L"
echo "==GZSERVER0=" >> "$L"; pgrep -ax gzserver >> "$L" 2>&1 || echo NONE >> "$L"
echo "==GZCLIENT0=" >> "$L"; pgrep -ax gzclient >> "$L" 2>&1 || echo NONE >> "$L"

# wait for gazebo to finish registering (cold start can exceed 120s)
for i in $(seq 1 60); do
  if gz model --query-models 2>/dev/null | grep -qi iris; then echo "==MODEL_UP_AT=${i}x3s=$(date -u +%H:%M:%S)==" >> "$L"; break; fi
  sleep 3
done

# list every topic (full = proves the master has registered px4 + cam plugins)
echo "==FULL_TOPIC_LIST_$i==" >> "$L"
timeout 30 rostopic list 2>&1 | grep -viE '^/(rosout|statistics|master|param|clock)' | head -70 >> "$L" 2>&1
echo "==ALL_COUNT=$(timeout 30 rostopic list 2>&1 | grep -viE '^/statistics$|^/clock$|^/param|^/master|^/rosout' | wc -l)==" >> "$L"
echo "==CAM_IMU_MATCH==" >> "$L"
timeout 30 rostopic list 2>&1 | grep -iE 'cam|image|imu|px4|mav' | head -24 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
