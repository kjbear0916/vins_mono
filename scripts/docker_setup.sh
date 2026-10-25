#!/usr/bin/env bash
# docker_setup.sh — Build and start the VINS research environment
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "── Building Docker image (this takes ~30 min on first run) ..."
cd "${SCRIPT_DIR}/docker"
docker build -t vins_research:latest .

echo ""
echo "── Environment built successfully!"
echo ""
echo "To start the environment:"
echo "  docker compose -f ${SCRIPT_DIR}/docker/docker-compose.yml up"
echo ""
echo "Then inside the container:"
echo "  source /opt/ros/noetic/setup.bash"
echo "  source /root/catkin_ws/devel/setup.bash"
echo ""
echo "To run experiments:"
echo "  bash /root/catkin_ws/src/vins_research/scripts/run_experiment.sh high 1.5 circle 1"