#!/bin/bash
L=/tmp/tumvi_end.$$.tmp
: > /tmp/tumvi_probe.dat
echo "==S=$(date -u +%H:%M:%S)==" >> /tmp/tumvi_probe.dat
# EuRoC 由 vision.in.tum.de 提供? 不。TUM-VI 才是 tum_in.tum.de。
# 但 VINS-Mono 的 config/tum 就是給 TUM-VI。先確認 config 上路徑 topic
echo "==TUMVI_CFG_TOPIC_LINE==" >> /tmp/tumvi_probe.dat
grep -nE 'imu_topic|image_topic|output_path|model_type|camera_name' /root/catkin_ws/src/VINS-Mono/config/tum/tum.yaml 2>/dev/null | head -8 >> /tmp/tumvi_probe.dat
echo "==TUMVI_DIR_LISTING==" >> /tmp/tumvi_probe.dat
ls /root/catkin_ws/src/VINS-Mono/config/tum/ >> /tmp/tumvi_probe.dat 2>&1
echo "==TUMVIPROBE_DOWNLOAD_BAG_HTTP==" >> /tmp/tumvi_probe.dat
# TUM-VI 官方資源也在 https 上;但我們已證明 vision 443 被 ETH fw 擋。
# 嘗試 HTTP (port 80) 直鏈 — 雖然我們知道 ETH 80 也被擋,但 TUM 是不同主機 vision.in.tum.de
timeout 20 wget -q -S -O /tmp/tumvi_probe.bag.part \
  "https://vision.in.tum.de/data/datasets/visual-inertial-dataset/downloads/room1_512_16.bag" \
  2>&1 | grep -iE 'HTTP/|content-length|Refused|failed|redirect' | head -8 >> /tmp/tumvi_probe.dat 2>&1
echo "==BAG_PART_BYTES==" >> /tmp/tumvi_probe.dat
stat -c%s /tmp/tumvi_probe.bag.part 2>/dev/null || echo 0 >> /tmp/tumvi_probe.dat
rm -f /tmp/tumvi_probe.bag.part
echo "==GH_ASL_DATASET_TOOLS_EUROC_URLS==" >> /tmp/tumvi_probe.dat
# dataset_tools clone 有 connect/manager 但沒有 EuRoC 直接鏈?
# 反而 VINS-Mono 的 GitHub 有人用 RELEASE 放 EuRoC bag。試搜
timeout 20 curl -sI https://github.com/HKUST-Aerial-Robotics/VINS-Mono/releases 2>&1 | grep -iE 'HTTP/|location' | head -3 >> /tmp/tumvi_probe.dat 2>&1
echo "==END=$(date -u +%H:%M:%S)==" >> /tmp/tumvi_probe.dat
cat /tmp/tumvi_probe.dat
