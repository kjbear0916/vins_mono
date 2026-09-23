# ROS2 節點影像 (Jazzy) — 依賴釘板, 建置放 runtime (workspace 是 volume)
FROM osrf/ros:jazzy-desktop

ENV WS=/root/disaster_drone_ws

# 橋接與影像處理工具列
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-jazzy-ros-gz \
        ros-jazzy-gz-ros2-control \
        ros-jazzy-cv-bridge \
        python3-pip python3-colcon-common-extensions \
        python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# 需求釘板 (ob #28/#29: 不 upgrade setuptools, 版本全部寫死)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    || { echo "pip install failed"; exit 1; }

ENV GZ_SIM_RESOURCE_PATH=${WS}/src/drone_bringup/worlds:${WS}/src/drone_bringup/models

CMD ["/root/disaster_drone_ws/docker/setup_ws.sh"]