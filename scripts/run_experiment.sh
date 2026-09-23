#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# run_experiment.sh — One-click experiment runner
#
# Usage:
#   ./run_experiment.sh <light> <speed> <trajectory> [repeat]
#
# Example:
#   ./run_experiment.sh high 1.5 circle 1
# ═══════════════════════════════════════════════════════

set -euo pipefail

# ─── Arguments ───
LIGHT="${1:?Usage: $0 <light:high|medium|low> <speed:0.5|1.5|3.0> <trajectory:circle|figure8> [repeat]}"
SPEED="${2:?Usage: $0 <light> <speed> <trajectory> [repeat]}"
TRAJECTORY="${3:?Usage: $0 <light> <speed> <trajectory> [repeat]}"
REPEAT="${4:-1}"

# ─── Paths ───
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="${PROJECT_DIR}/data"
BAG_DIR="${DATA_DIR}/rosbags"
WORLD_FILE="${PROJECT_DIR}/worlds/light_${LIGHT}.world"
CONFIG_FILE="${PROJECT_DIR}/config/sim_config.yaml"
FLIGHT_SCRIPT="${SCRIPT_DIR}/flight/waypoint_flight.py"

# ─── Setup ───
EXPERIMENT_ID="${LIGHT}_${SPEED}ms_${TRAJECTORY}_r${REPEAT}"
BAG_FILE="${BAG_DIR}/${EXPERIMENT_ID}.bag"

mkdir -p "${BAG_DIR}"

echo "╔══════════════════════════════════════════╗"
echo "║  VINS-Mono Simulation Experiment         ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Light:       ${LIGHT}"
echo "║  Speed:       ${SPEED} m/s"
echo "║  Trajectory:  ${TRAJECTORY}"
echo "║  Repeat:      ${REPEAT}"
echo "║  Experiment:  ${EXPERIMENT_ID}"
echo "╚══════════════════════════════════════════╝"

# ─── Source ROS ───
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash

# ─── Step 1: Kill any existing Gazebo ───
echo "[1/6] Cleaning up previous simulation..."
pkill -f gazebo || true
pkill -f px4 || true
pkill -f mavros || true
sleep 2

# ─── Step 2: Start Gazebo with specific world ───
echo "[2/6] Starting Gazebo with world: light_${LIGHT}"
roslaunch px4_sim px4_multi_agent.launch \
    world:="${WORLD_FILE}" \
    vehicle:=iris &
GAZEBO_PID=$!
sleep 8

# ─── Step 3: Start MAVROS ───
echo "[3/6] Starting MAVROS..."
rosrun mavros mavros_node \
    _fcu_url:=udp://:14556@localhost:14557 &
MAVROS_PID=$!
sleep 3

# ─── Step 4: Start VINS-Mono ───
echo "[4/6] Starting VINS-Mono estimator..."
roslaunch vins_mono vins_mono.launch \
    config_file:="${CONFIG_FILE}" &
VINS_PID=$!
sleep 5

# ─── Step 5: Start rosbag recording ───
echo "[5/6] Recording rosbag..."
rosbag record -O "${BAG_FILE}" \
    /vins_estimator/path \
    /vins_estimator/odometry \
    /vins_estimator/pose_graph/pose \
    /mavros/imu/data_raw \
    /camera/image_raw \
    /gazebo/model_states \
    /tf \
    /tf_static &
BAG_PID=$!
sleep 3

# ─── Step 6: Execute flight ───
echo "[6/6] Executing flight: ${TRAJECTORY} at ${SPEED} m/s..."
# Determine duration based on speed (ensure full trajectory traversal)
DURATION=60
python3 "${FLIGHT_SCRIPT}" \
    --trajectory "${TRAJECTORY}" \
    --speed "${SPEED}" \
    --radius 5.0 \
    --altitude 3.0 \
    --duration "${DURATION}"

# ─── Cleanup ───
echo "Stopping recording..."
kill ${BAG_PID} 2>/dev/null || true
sleep 2

echo "Shutting down nodes..."
kill ${VINS_PID} 2>/dev/null || true
kill ${MAVROS_PID} 2>/dev/null || true
kill ${GAZEBO_PID} 2>/dev/null || true
pkill -f gazebo || true
pkill -f px4 || true
sleep 2

echo "╔══════════════════════════════════════════╗"
echo "║  Experiment complete!                     ║"
echo "║  Bag file: ${BAG_FILE}"
echo "╚══════════════════════════════════════════╝"
