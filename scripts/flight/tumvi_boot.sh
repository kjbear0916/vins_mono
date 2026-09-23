#!/bin/bash
L=/tmp/tumvi_boot.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

echo "==TUMVI_INDEX_RELAYS==" >> "$L"
# 先驗證目錄清單那顆真的可達 + 是我們要的 room1
for base in \
  "https://vision.in.tum.de/tumvi/calibrated/512_16/" \
  "https://vision.in.tum.de/tumvi/calibrated/512_16/dataset-room1_512_16.bag" \
  "http://vision.in.tum.de/tumvi/calibrated/512_16/dataset-room1_512_16.bag" \
; do
  echo "--URL=$base--" >> "$L"
  timeout 16 curl -sIR "$base" 2>&1 | grep -iE 'HTTP/|location|content-length' | head -4 >> "$L" 2>&1
done

echo "==TUMVI_CFG_DIFF_CHECK==" >> "$L"
# VINS tum_config 的 output_path 是 /home/tony-ws1/output —— 驗證那棵目錄,免得老坑
grep -nE 'output_path|imu_topic|image_topic' /root/catkin_ws/src/VINS-Mono/config/tum/tum_config.yaml 2>&1 | head -6 >> "$L" 2>&1

echo "==DO_DOWNLOAD_ROOM1_2_2G==" >> "$L"
cd /root/euroc 2>/dev/null || mkdir -p /root/euroc && cd /root/euroc
# 用 wget -c 續傳;只抓 room1(2.2G)這次先驗真流。計時 + .part 結束仍測 bytes
echo "DL_START=$(date -u +%H:%M:%S)" >> "$L"
timeout 55 wget -q -c -T 25 -O dataset-room1_512_16.bag \
  "https://vision.in.tum.de/tumvi/calibrated/512_16/dataset-room1_512_16.bag" 2>&1 >> "$L" 2>&1
if [ -f dataset-room1_512_16.bag ]; then
  echo "ROOM1_BYTES=$(stat -c%s dataset-room1_512_16.bag)" >> "$L"
else
  echo "ROOM1_BAG_ABSENT" >> "$L"
fi
echo "DL_END=$(date -u +%H:%M:%S)" >> "$L"
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
