#!/bin/bash
L=/tmp/tviprobe.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
echo "==TUMVI_CFG_CONFIRM==" >> "$L"
sed -n '1,55p' /root/catkin_ws/src/VINS-Mono/config/tum/tum_config.yaml | grep -vE '^\s*#|^\s*$' | grep -E 'imu_topic|image_topic|cam0|cam1|output_path|imu_factor|imu1|fisheye|model_type|estimate_extrinsic' | head -12 >> "$L" 2>&1
echo "==TUMVI_TCP_443==" >> "$L"
timeout 15 bash -c 'exec 3<>/dev/tcp/vision.in.tum.de/443 && echo TUV443_OPEN || echo TUV443_FAIL' >> "$L" 2>&1
echo "==TUMVI_TCP_80==" >> "$L"
timeout 15 bash -c 'exec 3<>/dev/tcp/vision.in.tum.de/80 && echo TUV80_OPEN || echo TUV80_FAIL' >> "$L" 2>&1
echo "==TUMVI_HTTPS_DATASET_PAGE_HEAD==" >> "$L"
timeout 20 curl -sIL "https://vision.in.tum.de/data/datasets/visual-inertial-dataset" 2>&1 | grep -iE 'HTTP/|content-length|location' | head -6 >> "$L" 2>&1
echo "==TUMVI_DIRECT_HTTPS_HTTP_BAG_CANDIDATES==" >> "$L"
for u in \
 "https://vision.in.tum.de/data/datasets/visual-inertial-dataset/dataset1/room1/images.zip?path=room1/images.zip" \
 "http://vm1.cs.tum.edu/data/datasets/visual-inertial-dataset/room1/room1_512_16.bag" \
 "https://vision.in.tum.de/rgbd/dataset/viusi/room1_512_16.bag" \
; do
  echo "--u=$u" >> "$L"
  timeout 16 wget -q -O /tmp/tvprobe.part --spider "$u" 2>&1 | grep -iE 'HTTP/|Length:|Length:' >> "$L" 2>&1
done >> "$L" 2>&1
echo "==QCOM_VI_KVM_4K_NO_NEED==" >> "$L"
rm -f /tmp/tvprobe.part
echo ==END=$(date -u +%H:%M:%S)== >> "$L"
cat "$L"
