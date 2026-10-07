#!/usr/bin/env python3
"""
Extract VINS estimated trajectory and ground truth trajectory from a rosbag,
and save both in TUM format for EVO evaluation.

Usage:
    python3 extract_trajectories.py --bag <file.bag>
"""
import argparse
import os
import sys
import csv
import math
import numpy as np
import rosbag
import rospy
from nav_msgs.msg import Path
from nav_msgs.msg import Odometry
from gazebo_msgs.msg import ModelStates
from geometry_msgs.msg import PoseStamped, Quaternion


def quat_to_rot(q):
    """Convert quaternion to rotation matrix."""
    x, y, z, w = q.x, q.y, q.z, q.w
    return np.array([
        [1 - 2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1 - 2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1 - 2*(x*x+y*y)]
    ])


def quat_to_euler(q):
    """Convert quaternion to euler angles."""
    x, y, z, w = q.x, q.y, q.z, q.w
    t0 = 2.0 * (w * x + y * z)
    t1 = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(t0, t1)
    t2 = 2.0 * (w * y - z * x)
    t2 = max(-1.0, min(1.0, t2))
    pitch = math.asin(t2)
    t3 = 2.0 * (w * z + x * y)
    t4 = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(t3, t4)
    return roll, pitch, yaw


def extract_vins_path(bag, topic, output_path):
    """Extract VINS estimated trajectory as TUM format (deduplicated by timestamp)."""
    pose_map = {}
    for topic, msg, t in bag.read_messages(topics=[topic]):
        if hasattr(msg, "poses") and getattr(msg, "poses"):
            # nav_msgs/Path: each message contains keyframe poses up to current time
            for pose in msg.poses:
                timestamp = pose.header.stamp.to_sec()
                p = pose.pose.position
                q = pose.pose.orientation
                pose_map[timestamp] = [timestamp, p.x, p.y, p.z, q.x, q.y, q.z, q.w]
        elif hasattr(msg, "pose") and hasattr(msg, "twist"):
            # nav_msgs/Odometry
            timestamp = msg.header.stamp.to_sec()
            p = msg.pose.pose.position
            q = msg.pose.pose.orientation
            pose_map[timestamp] = [timestamp, p.x, p.y, p.z, q.x, q.y, q.z, q.w]

    rows = sorted(pose_map.values(), key=lambda r: r[0])
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f, delimiter=' ')
        for row in rows:
            writer.writerow([f"{row[0]:.9f}" if isinstance(row[0], float) else row[0]] +
                            [f"{v:.9f}" for v in row[1:]])
    print(f"VINS trajectory: {len(rows)} poses -> {output_path}")
    return len(rows)


def extract_gazebo_gt(bag, model_name='iris', output_path=None):
    """Extract ground truth trajectory from /gazebo/model_states."""
    rows = []
    for topic, msg, t in bag.read_messages(topics=['/gazebo/model_states']):
        found = [i for i, n in enumerate(msg.name) if model_name in n]
        if not found:
            continue
        idx = found[0]
        timestamp = t.to_sec()
        p = msg.pose[idx].position
        q = msg.pose[idx].orientation
        rows.append([timestamp, p.x, p.y, p.z, q.x, q.y, q.z, q.w])

    rows.sort(key=lambda r: r[0])
    if output_path is None:
        raise ValueError("output_path is required")
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f, delimiter=' ')
        for row in rows:
            writer.writerow([f"{row[0]:.9f}" if isinstance(row[0], float) else row[0]] +
                            [f"{v:.9f}" for v in row[1:]])
    print(f"Ground truth: {len(rows)} poses -> {output_path}")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description='Extract trajectories from rosbag')
    parser.add_argument('--bag', required=True, help='Input rosbag file')
    parser.add_argument('--model', default='iris', help='Gazebo model name')
    parser.add_argument('--vins-topic', default='/vins_estimator/path',
                        help='VINS path topic')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory (default: same as bag)')
    args = parser.parse_args()

    if not os.path.exists(args.bag):
        print(f"ERROR: Bag file not found: {args.bag}")
        sys.exit(1)

    out_dir = args.output_dir if args.output_dir else os.path.dirname(args.bag)
    os.makedirs(out_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(args.bag))[0]

    # Extract VINS trajectory
    vins_topic = args.vins_topic
    vins_path = os.path.join(out_dir, base + '_vins.txt')
    with rosbag.Bag(args.bag, 'r') as bag:
        # Try Topic message type detection: some bags use /vins_estimator/odometry
        try_count = extract_vins_path(bag, vins_topic, vins_path)
        if try_count == 0:
            print("No poses on /vins_estimator/path, trying /vins_estimator/odometry...")
            vins_path = os.path.join(out_dir, base + '_vins.txt')
            extract_vins_path(bag, '/vins_estimator/odometry', vins_path)

        # Extract ground truth
        gt_path = os.path.join(out_dir, base + '_gt.tum')
        count = extract_gazebo_gt(bag, args.model, gt_path)
    if count == 0:
        print("WARNING: No ground truth found for model '{}'".format(args.model))

    print("\nDone. Files:")
    print(f"  VINS: {vins_path}")
    print(f"  GT:   {gt_path}")


if __name__ == '__main__':
    main()