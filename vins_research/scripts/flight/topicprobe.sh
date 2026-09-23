#!/bin/bash
L=/tmp/topicprobe.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

echo "==KITTI_CFG_HEAD==" >> "$L"
sed -n '1,30p' /root/catkin_ws/src/VINS-Mono/config/kitti_odom/kitti_odom.yaml 2>/dev/null | grep -vE '^\s*#|^\s*$' >> "$L" 2>&1

echo "==KITTI_CFG_KEYS==" >> "$L"
grep -nE 'imu_topic|image_topic|output_path|imu_factor|cam0_|cam1_|input_file' /root/catkin_ws/src/VINS-Mono/config/kitti_odom/kitti_odom.yaml 2>/dev/null >> "$L" 2>&1

echo "==KITTI_DEV_HTTP==" >> "$L"
timeout 18 bash -c 'exec 3<>/dev/tcp/www.cvlibs.net/80 && echo TCP80_OPEN || echo TCP80_FAIL' >> "$L" 2>&1

echo "==KITTI_MAIN_HTTPS==" >> "$L"
timeout 18 curl -sI "https://www.cvlibs.net/datasets/kitti/" 2>&1 | grep -iE 'HTTP/|location|server' | head -2 >> "$L" 2>&1

echo "==KITTI_ODOM_HTTP==" >> "$L"
for u in "http://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0005/2011_09_26_drive_0005_sync.zip" "http://www.cvlibs.net/download.php?file=raw_data_downloader.zip"; do
  timeout 12 curl -sI "$u" 2>&1 | grep -iE 'HTTP/|content-length|location' | head -2 >> "$L" 2>&1
 done >> "$L" 2>&1

echo "==EUROC_CFG_HEAD==" >> "$L"
sed -n '1,22p' /root/catkin_ws/src/VINS-Mono/config/euroc/euroc_config.yaml 2>/dev/null | grep -vE '^\s*#|^\s*$' | head -12 >> "$L" 2>&1

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
