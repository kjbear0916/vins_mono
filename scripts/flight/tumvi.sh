#!/bin/bash
L=/tmp/tumvi.log; : > "$L"
echo "==DT_CLONE_STATE==" >> "$L"
ls -d /tmp/dtools 2>/dev/null && ls /tmp/dtools | head -20 >> "$L" 2>&1 || echo "NO_DTOOLS_CLONE" >> "$L"

echo "==DT_EUROC_SCRIPT==" >> "$L"
find /tmp/dtools -iname '*.py' 2>/dev/null | head -10 >> "$L" 2>&1
grep -rniE 'euroc|rosbag|rosparam|download_$$|MULTI_DOWNLOAD' /tmp/dtools/*.py /tmp/dtools/euroc/*.py 2>/dev/null | grep -iE 'http|url|rosbag|eval_odom' | head -8 >> "$L" 2>&1

echo "==TUMVI_CFG_GLOB==" >> "$L"
find /root/catkin_ws/src/VINS-Mono/config -iname '*tum*' 2>/dev/null >> "$L" 2>&1

echo "==TUMVI_CFG_TOPICS==" >> "$L"
T=$(find /root/catkin_ws/src/VINS-Mono/config -iname 'tum_vi.yaml' | head -1)
echo "path=$T" >> "$L"
[ -n "$T" ] && grep -nE 'imu_topic|image_topic|output_path|imu_scale|imu1_scale|tag_page' "$T" | head -8 >> "$L" 2>&1

echo "==KITTI_GITHUB_RELEASE_HEAD==" >> "$L"
timeout 15 wget -q --spider "https://github.com/ethz-asl/VINS-Mono/releases/tag/euroc" 2>&1 | grep -iE 'HTTP/*' >> "$L" 2>&1
echo "==DONE=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
