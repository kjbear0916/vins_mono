#!/bin/bash
set +u
echo "== marker_detector processes =="
ps aux | grep -E 'marker_detector' | grep -v grep | awk '{print $2, $13, $14}'
echo "== uwb/trilat/pose_fusion procs =="
ps aux | grep -E 'uwb|pose_fusion|trilat' | grep -v grep | awk '{print $2, $13, $14}'
echo
echo "== marker_detector source: detection publishing =="
sed -n '1,200p' /workspace/disaster_drone_ws/src/marker_localization/marker_localization/marker_detector_node.py | grep -nE 'publish|publisher|detected|marker_id|confidence|create_publisher' | head -20