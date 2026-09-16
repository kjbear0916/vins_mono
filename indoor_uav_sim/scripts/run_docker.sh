#!/bin/bash
# Docker build and run script

set -e
cd "$(dirname "$0")/.."

echo "=== Building Docker images ==="
docker compose -f docker/docker-compose.yml build

echo "=== Starting PX4 + Gazebo ==="
docker compose -f docker/docker-compose.yml up -d px4_gazebo

echo "Waiting 30s for PX4 to initialize..."
sleep 30

echo "=== Starting ROS2 nodes ==="
docker compose -f docker/docker-compose.yml up ros2_nodes
