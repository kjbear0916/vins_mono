#!/bin/bash
set +u
echo "== grep BridgeConfig key expectations =="
grep -rnE 'ros_type_name|gz_type_name|ros_msg_type|gz_msg_type' /opt/ros/jazzy/include/ros_gz_bridge/ 2>/dev/null | head -20
grep -rnE 'ros_type_name|gz_type_name|ros_msg_type|gz_msg_type' /opt/ros/jazzy/share/ros_gz_bridge/ 2>/dev/null | head
echo "== example yaml shipped with distro =="
find /opt/ros/jazzy/share/ros_gz_bridge -name '*.yaml' -o -name '*.yml' 2>/dev/null | head
cat /opt/ros/jazzy/share/ros_gz_bridge/*.yaml 2>/dev/null | head -30