#!/bin/bash
L=/tmp/kittiprobe.log; : > "$L"
echo "==KITTI_CFG_IMU_TOPIC==" >> "$L"
grep -nE 'imu_topic|image0_topic|image1_topic|output_path|imu_factor|same_imu|imu_lib' /root/catkin_ws/src/VINS-Mono/config/kitti_odom/kitti_odom.yaml >> "$L" 2>&1
echo "==KITTI_ODOM_BAG_FETCH_DATA_BYTES==" >> "$L"
# minimal real HTTP fetch through port 80 (the open one): measure actual bytes
rm -f /root/kprobe.idx
timeout 30 wget -q -O /root/kprobe.idx "http://www.cvlibs.net/datasets/kitti/eval_odometry.php" 
S=0; [ -f /root/kprobe.idx ] && S=$(stat -c%s /root/kprobe.idx)
echo "bytes=$S" >> "$L"
echo "==DONE=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
