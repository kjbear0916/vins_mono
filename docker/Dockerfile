FROM osrf/ros:noetic-desktop-full

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=noetic
ENV PX4_VERSION=v1.14.3

# ─── PX4 dependencies ───
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git wget ninja-build \
    libopencv-dev libeigen3-dev \
    libgoogle-glog-dev libgflags-dev \
    libatlas-base-dev libsuitesparse-dev \
    python3-pip python3-catkin-tools \
    lsb-release rsync \
    && rm -rf /var/lib/apt/lists/*

# ─── Ceres Solver 1.14.0 (VINS-Mono compatible) ───
RUN cd /tmp && \
    wget -q https://github.com/ceres-solver/ceres-solver/archive/1.14.0.tar.gz && \
    tar xzf 1.14.0.tar.gz && cd ceres-solver-1.14.0 && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF && \
    make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/ceres-solver-1.14.0 /tmp/1.14.0.tar.gz

# ─── PX4-Autopilot ───
RUN mkdir -p /root/catkin_ws/src && \
    cd /root && \
    git clone --depth 1 --branch ${PX4_VERSION} https://github.com/PX4/PX4-Autopilot.git && \
    cd PX4-Autopilot && \
    bash Tools/setup/ubuntu.sh --no-nuttx --no-sim-tools && \
    make px4_sitl_default

# ─── MAVROS ───
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-noetic-mavlink ros-noetic-geographic-msgs \
    ros-noetic-gps-common libgeographic-dev \
    && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /root/catkin_ws/src && \
    wget -q https://github.com/mavlink/mavros/archive/refs/tags/1.21.1.tar.gz -O /tmp/mavros.tar.gz && \
    tar xzf /tmp/mavros.tar.gz -C /root/catkin_ws/src && \
    mv /root/catkin_ws/src/mavros-1.21.1 /root/catkin_ws/src/mavros && \
    wget -q https://github.com/ethz-asl/mav_comm/archive/refs/heads/master.tar.gz -O /tmp/mav_comm.tar.gz && \
    tar xzf /tmp/mav_comm.tar.gz -C /root/catkin_ws/src && \
    mv /root/catkin_ws/src/mav_comm-master /root/catkin_ws/src/mav_comm && \
    rm -f /tmp/mavros.tar.gz /tmp/mav_comm.tar.gz && \
    cd /root/catkin_ws && \
    /bin/bash -c "source /opt/ros/${ROS_DISTRO}/setup.bash && catkin_make -DCMAKE_BUILD_TYPE=Release -j$(nproc)"

# ─── VINS-Mono ───
RUN wget -q https://github.com/HKUST-Aerial-Robotics/VINS-Mono/archive/refs/heads/master.tar.gz -O /tmp/vins.tar.gz || \
    wget -q https://github.com/HKUST-Aerial-Robotics/VINS-Mono/archive/refs/heads/main.tar.gz -O /tmp/vins.tar.gz && \
    mkdir -p /root/catkin_ws/src && \
    tar xzf /tmp/vins.tar.gz -C /root/catkin_ws/src && \
    mv /root/catkin_ws/src/VINS-Mono-* /root/catkin_ws/src/VINS-Mono && \
    rm -f /tmp/vins.tar.gz && \
    cd /root/catkin_ws && \
    /bin/bash -c "source /opt/ros/${ROS_DISTRO}/setup.bash && catkin_make -DCMAKE_BUILD_TYPE=Release -j$(nproc)"

# ─── Python analysis tools ───
RUN pip3 install --upgrade 'pip<25' && \
    pip3 install --force-reinstall --no-deps 'numpy>=1.21.0,<2.0' && \
    pip3 install 'setuptools<70' && \
    pip3 install 'pandas>=1.3.0,<3.0' evo matplotlib seaborn scipy

# ─── Baked simulation runtime assets (2026-10-11) ───
# Not produced by the stock PX4 build (and previously applied by hand inside the
# container, lost on every recreate): the gazebo-classic plugins, the rendered
# jinja models, the custom vins_demo world + vins_props model, the GeographicLib
# geoid, and three sitl_run.sh patches. setup_sim_assets.sh is idempotent and can
# also be re-run in a live container after a recreate. Placed last so changing an
# asset does not invalidate the expensive PX4 / MAVROS / VINS layers.
COPY setup_sim_assets.sh fix_sitl_run.py fix_ros1_plugins.py fix_xvfb.py /tmp/sim_assets/
COPY assets/ /tmp/sim_assets/assets/
RUN ASSETS_DIR=/tmp/sim_assets/assets bash /tmp/sim_assets/setup_sim_assets.sh

# ─── Volume mounts ───
VOLUME ["/root/catkin_ws/src/vins_research", "/data"]

# ─── Entry ───
WORKDIR /root/catkin_ws
CMD ["/bin/bash"]
