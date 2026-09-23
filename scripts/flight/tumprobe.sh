#!/bin/bash
L=/tmp/tumprobe.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

echo "==TUM_CFG_TOPICS_AND_OUT==" >> "$L"
grep -nE 'imu_topic|image0_topic|image1_topic|output_path|imu_factor|same_imu|tag_params|cam0|cam1|cam2' /root/catkin_ws/src/VINS-Mono/config/tum/tum_config.yaml >> "$L" 2>&1

echo "==TUM_CFG_HEAD30==" >> "$L"
sed -n '1,30p' /root/catkin_ws/src/VINS-Mono/config/tum/tum_config.yaml | grep -vE '^\s*#|^\s*$' >> "$L" 2>&1

echo "==TUM_VI_HTTP_443==" >> "$L"
timeout 18 bash -c 'exec 3<>/dev/tcp/vision.in.tum.de/443 && echo TUM443_OPEN || echo TUM443_FAIL' >> "$L" 2>&1
echo "==TUM_VI_HTTP_80==" >> "$L"
timeout 18 bash -c 'exec 3<>/dev/tcp/vision.in.tum.de/80 && echo TUM80_OPEN || echo TUM80_FAIL' >> "$L" 2>&1
echo "==TUM_VI_ROSCALIB_GET==" >> "$L"
timeout 22 wget -q -O /tmp/tumvi_probe.html -S "http://vision.in.tum.de/data/datasets/visual-inertial-dataset" 2>&1 | grep -iE 'HTTP/' >> "$L" 2>&1
[ -s /tmp/tumvi_probe.html ] && echo "TUMVI_HTML_BYTES=$(stat -c%s /tmp/tumvi_probe.html)" >> "$L"

echo "==TUMVI_ROSCALIB2_ZIP_HTTP==" >> "$L"
timeout 22 wget -q -O /tmp/tumvi_zip_probe -S "http://vision.in.tum.de/data/datasets/visual-inertial-dataset/dataset1/opensource.zip" 2>&1 | grep -iE 'HTTP/|content-length' >> "$L" 2>&1
[ -s /tmp/tumvi_zip_probe ] && echo "TUMVI_ZIP_BYTES=$(stat -c%s /tmp/tumvi_zip_probe)" >> "$L"

echo "==END=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
