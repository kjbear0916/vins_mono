# PX4 SITL + Gazebo Harmonic 影像
# 注意 (ob #25): make px4_sitl gz_xxx 是「編譯＋啟動」雙效目標, 在 RUN 中執行
# 會掛住 build。影像建置只做「純編譯」, 啟動交給 entrypoint_sitl.sh。
FROM osrf/ros:jazzy-desktop

ENV PX4_ROOT=/root/PX4-Autopilot
ENV PX4_VERSION=v1.16.0
ENV PX4_HOME_LAT=25.0
ENV PX4_HOME_LON=-80.0
ENV PX4_HOME_ALT=0.0

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# ros_gz bridge 工具列
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-jazzy-ros-gz \
        ros-jazzy-gz-ros2-control \
        python3-pip python3-venv git cmake \
    && rm -rf /var/lib/apt/lists/*

# PX4 原始碼 + 依賴 (v1.16 支援 Ubuntu 24.04 / Gazebo Harmonic)
RUN git clone --depth 1 --branch ${PX4_VERSION} https://github.com/PX4/PX4-Autopilot.git ${PX4_ROOT}

WORKDIR ${PX4_ROOT}

# 只裝模擬所需依賴; --no-nuttx 跳過嵌入式工具鏈; --no-sim-tools 沿用影像內 Gazebo
RUN bash ./Tools/setup/ubuntu.sh --no-nuttx --no-sim-tools \
    || { echo "PX4 setup script failed"; exit 1; }

# 純編譯 (不起動)。cmake/ninja 產物到 build/px4_sitl_default/
RUN git submodule update --init --recursive
RUN make px4_sitl_default || { echo "PX4 build failed"; exit 1; }

ENV GZ_SIM_RESOURCE_PATH=${PX4_ROOT}/Tools/simulation/gz/models
ENV PX4_SIM_SPEED_FACTOR=1.0

CMD ["/root/disaster_drone_ws/docker/entrypoint_sitl.sh"]