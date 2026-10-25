#!/bin/bash
L=/tmp/kcfg.log; : > "$L"
echo "==ALL_VINS_CONFIGS==" >> "$L"
ls /root/catkin_ws/src/VINS-Mono/config/ >> "$L" 2>&1
echo "==KITTI_YAML_SEARCH==" >> "$L"
find /root/catkin_ws/src/VINS-Mono/config -iname '*kitti*' -o -iname '*odom*' >> "$L" 2>&1
echo "==KITTI_ODOM_YAML_DIAG==" >> "$L"
K=$(find /root/catkin_ws/src/VINS-Mono/config -iname 'kitti_odom.yaml' | head -1)
echo "path=$K" >> "$L"
[ -n "$K" ] && grep -nE 'imu_topic|image0_topic|image1_topic|input_file|imu_factor|pre_integration|output_path' "$K" >> "$L" 2>&1
echo "==KITTI_RAW_80_AGAIN==" >> "$L"
timeout 12 wget -q -O /tmp/k_probe -S "http://www.cvlibs.net/datasets/kitti/eval_odometry.php" 2>&1 | grep -iE 'HTTP/' >> "$L" 2>&1
echo "==MH01_ETH_80_PATH==" >> "$L"
# ETH old bag host still on :80 ? probe ONE real bag path
timeout 15 wget -q -O /tmp/mh_probe -S "http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_01_easy/MH_01_easy.bag" 2>&1 | grep -iE 'HTTP/|content-type|content-length' | head -acc >> "$L" 2>&1
echo "==END=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
