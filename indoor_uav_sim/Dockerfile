# Disaster-drone indoor rescue simulation — Phase 0..7 build image.
#
# Base: ROS2 Jazzy on Ubuntu 24.04 (includes Gazebo Harmonic runtime).
# Adds PX4-Autopilot SITL (built against Gazebo Harmonic) + this workspace.
#
# Build lessons applied (obs #0025/#0026/#0027/#0028/#0029):
#   * PX4 `make px4_sitl <model>` launches an interactive console and hangs
#     Docker builds forever -> build ONLY via cmake here; the interactive sim
#     is started at runtime in the compose service (which is its normal mode).
#   * Never chain `|| true && ...` (shell precedence silently propagates
#     failures) -> gate the build with a separate `test -x` line.
#   * git clone pinnings by tag (no default-branch migration guesswork);
#     GIT_LFS_SKIP_SMUDGE avoids LFS fetch/auth surprises.
#   * pip on Ubuntu 24.04 is externally managed -> --break-system-packages,
#     with exact version pins (strict pip version parsing).

FROM osrf/ros:jazzy-desktop

ENV DEBIAN_FRONTEND=noninteractive
ENV ORIG_ROS_DISTRO=jazzy
ENV WS=/workspace/disaster_drone_ws

# Correct the ros_entrypoint.sh ROS_DISTRO default is restored inside entrypoint.

# ---------------------------------------------------------------- apt base
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl git build-essential cmake ninja-build pkg-config \
    python3-colcon-common-extensions python3-rosdep python3-pip \
    python3-empy python3-jsonschema python3-packaging python3-setuptools \
    ccache lsb-release sudo \
    libeigen3-dev \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------ PX4 SITL (build only)
# PX4 v1.17.0 is the stable release that targets Gazebo Harmonic on 24.04.
# Clone by explicit tag; skip LFS smudge (assets are optional for SITL).
RUN git clone --depth 1 --branch v1.17.0 \
    https://github.com/PX4/PX4-Autopilot.git /opt/PX4-Autopilot && \
    cd /opt/PX4-Autopilot && \
    git submodule update --init --recursive --depth 1

# PX4 native toolchain (Ubuntu 24.04 / noble). The script also installs
# Gazebo Harmonic libs. pip steps inside it may trip on the externally-managed
# environment; we tolerate that here and re-do our own pip installs later.
RUN cd /opt/PX4-Autopilot && \
    (bash Tools/setup/ubuntu.sh --no-nuttx </dev/null >/tmp/px4_setup.log 2>&1 || true)

# Build ONLY the SITL binaries (config px4_sitl_default). No simulator run,
# no interactive px4 console -> cannot hang the build.
RUN cd /opt/PX4-Autopilot && \
    cmake -S . -B build/px4_sitl_default -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DCONFIG=px4_sitl_default >/tmp/px4_cmake.log 2>&1 && \
    cmake --build build/px4_sitl_default -j$(nproc) >/tmp/px4_build.log 2>&1 || \
    (tail -c 4000 /tmp/px4_cmake.log; tail -c 4000 /tmp/px4_build.log; exit 1)
RUN test -x /opt/PX4-Autopilot/build/px4_sitl_default/bin/px4 \
    && echo "PX4 SITL binary present" || (echo "PX4 binary missing"; exit 1)

# ------------------------------------------------------------ python deps
# apt-installed numpy/scipy/opencv carry no RECORD, so pip --ignore-installed
# replaces them without an uninstall round-trip.
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages --ignore-installed --no-cache-dir -r /tmp/requirements.txt

# ------------------------------------------------------------- workspace
WORKDIR ${WS}
COPY src/ ${WS}/src/

# colcon build must see an installable ament workspace. rosdep is skipped:
# all dependencies are declared in the packages and installed above.
RUN . /opt/ros/jazzy/setup.sh && \
    cd ${WS} && \
    colcon build --symlink-install --event-handlers console_cohesion+ || \
    (echo "colcon build failed"; exit 1)

# --------------------------------------------------------------- entry
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]