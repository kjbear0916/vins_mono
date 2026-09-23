#!/bin/bash
# 自錄路徑 Phase-1 門檻:sim 內必須有 sensor_msgs/Image + Imu 真 publisher。
# 一次原子:殺舊 sim -> fresh 拉起 -> 等 px4 up -> 列 topic -> 對候選 topic
# 連續讀 3 次 bytes(必須>0 且 遞增)才算「有源可錄」。全在單一檔案執行。
L=/tmp/simaudit.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

pkill -x gzserver; pkill -x px4; pkill -f sitl_run.sh 2>/dev/null
sleep 4
cd /root/PX4-Autopilot/build/px4_sitl_default
nohup bash /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh \
  /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 none iris_fpv_cam empty \
  /root/PX4-Autopilot /root/PX4-Autopilot/build/px4_sitl_default \
  > /tmp/simaudit_sim.log 2>&1 &
echo "==SIM_LAUNCHED=$(date -u +%H:%M:%S)=" >> "$L"

for i in $(seq 1 60); do
  pgrep -x px4 >/dev/null && break
  ps -eo cmd | grep -q 'bin/px4 none iris' && break
  sleep 2
done
echo "==PX4_UP_AFTER_$((i*2))s=$(date -u +%H:%M:%S)=" >> "$L"
ps -eo pid,etimes,cmd | grep -E 'bin/px4|gzserver' | grep -v grep >> "$L" 2>&1
echo "==WAIT_TOPICS_CNT=+12s==" >> "$L"
sleep 12
echo "==TOPIC_LIST_SAMPLE==" >> "$L"
timeout 25 rostopic list 2>&1 | grep -viE 'rosout|statistics' | head -40 >> "$L" 2>&1
echo "==IMU_AND_IMAGE_TOPICS==" >> "$L"
timeout 25 rostopic list 2>&1 | grep -iE 'imu|image|cam|mavros/imu' >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
