#!/bin/bash
L=/tmp/tumvi.reach; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

echo "==TUMVI_HOST_TCP80==" >> "$L"
timeout 18 bash -c 'exec 3<>/dev/tcp/vision.in.tum.de/80 && echo TUMVI_80_OPEN || echo TUMVI_80_FAIL' >> "$L" 2>&1

echo "==TUMVI_HOST_TCP443==" >> "$L"
timeout 18 bash -c 'exec 3<>/dev/tcp/vision.in.tum.de/443 && echo TUMVI_443_OPEN || echo TUMVI_443_FAIL' >> "$L" 2>&1

echo "==TUMVI_DL_STATIC_HTTP==" >> "$L"
# 官方鏡像: tumvi 的變電與 MH-01 相同結構, host 為 vision.in.tum.de (miTUM, 非 ETHZ)
for p in \
 "https://vision.in.tum.de/data/datasets/visual-inertial-dataset/downloads/room1_calib_cam_imu.bag" \
 "http://vision.in.tum.de/data/datasets/visual-inertial-dataset/room1/room1_512_16.bag" \
 ; do
  echo "--PATH=$p--" >> "$L"
  timeout 22 curl -sIL "$p" 2>&1 | grep -iE 'HTTP/|content-length|location' | head -4 >> "$L" 2>&1
done

echo "==TUMVI_ROOM1_512_16_HTTP_HEAD==" >> "$L"
timeout 25 wget -q -S -O /dev/null --spider "http://vm1.cs.tum.edu/data/datasets/visual-inertial-dataset/room1/room1_512_16.bag" 2>&1 \
  | grep -iE 'HTTP/|content-length|Length' | head -6 >> "$L" 2>&1
echo "==DONE=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
