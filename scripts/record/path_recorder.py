#!/usr/bin/env python3
"""Record VINS path + ground truth pose to CSV during a trial.

Usage:
    python3 path_recorder.py --duration 45 --out /tmp/trial_001_path.csv
Subscribes to:
    /vins_estimator/path            (nav_msgs/Path)
    /mavros/local_position/pose     (geometry_msgs/PoseStamped)
    /vins_estimator/imu_propagate   (optional, skipped if absent)
Writes rows: sim_t, vins_x, vins_y, vins_z, vins_n, gt_x, gt_y, gt_z
using latest available values when the corresponding topic is silent.
"""

import rospy
import argparse
import math
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped

STATE = {
    "vins": None,   # (x, y, z)
    "vins_n": 0,
    "gt": None,     # (x, y, z)
}


def path_cb(msg):
    if not msg.poses:
        return
    p = msg.poses[-1].pose.position
    STATE["vins"] = (p.x, p.y, p.z)
    STATE["vins_n"] = len(msg.poses)


def pose_cb(msg):
    p = msg.pose.position
    STATE["gt"] = (p.x, p.y, p.z)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=45.0)
    ap.add_argument("--out", default="/tmp/trial_path.csv")
    args = ap.parse_args()

    rospy.init_node("path_recorder", anonymous=True)
    rospy.Subscriber("/vins_estimator/path", Path, path_cb)
    rospy.Subscriber("/mavros/local_position/pose", PoseStamped, pose_cb)

    out = open(args.out, "w")
    out.write("sim_t,vins_x,vins_y,vins_z,vins_n,gt_x,gt_y,gt_z\n")
    out.flush()

    t0 = rospy.Time.now()
    rate = rospy.Rate(10)
    wrote = 0
    while not rospy.is_shutdown():
        el = (rospy.Time.now() - t0).to_sec()
        if el >= args.duration:
            break
        v = STATE["vins"]
        g = STATE["gt"]
        if v is not None or g is not None:
            row = "{:.3f},{},{},{},{},{},{},{}\n".format(
                el,
                "" if v is None else "{:.4f}".format(v[0]),
                "" if v is None else "{:.4f}".format(v[1]),
                "" if v is None else "{:.4f}".format(v[2]),
                STATE["vins_n"],
                "" if g is None else "{:.4f}".format(g[0]),
                "" if g is None else "{:.4f}".format(g[1]),
                "" if g is None else "{:.4f}".format(g[2]),
            )
            out.write(row)
            wrote += 1
        rate.sleep()
    out.close()
    print(f"RECORDER_DONE rows={wrote} vins_final={STATE['vins']}")


if __name__ == "__main__":
    main()