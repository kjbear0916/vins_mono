#!/bin/bash
set +u
echo "== YAML entry keys expected by bridge_config =="
find / -path '*ros_gz_bridge*bridge_config*' \( -name '*.cpp' -o -name '*.c' \) 2>/dev/null | head
grep -rnE '\["[a-z_]+"\]' /opt/ros/jazzy/include/ros_gz_bridge/ 2>/dev/null | head -20