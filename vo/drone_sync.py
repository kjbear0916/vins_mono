"""Drone VO time-sync skeleton.

Maps ESP32-camera frame timestamps and a receiver-side log (camera IMU / OSD
/ RC) onto the VO keyframe trajectory so downstream fusion or BA can reason
in a common time base.

The drone logs its own wall-clock stamps (usually ms since boot or NMEA time).
The ESP32 stream is delivered over WiFi with variable latency, so the camera
frame that visually matches a log line is NOT the one the timestamp was
written for.  This module provides:

  * `align_frames(log_ts, cam_ts)`  -- nearest-neighbour / linear-interp map
    between the two clock domains (core, pure-numpy, unit-testable).
  * `read_receiver_log`            -- tolerant CSV reader for OSD/IMU/RC logs.
  * `SyncTrajectory`               -- merges VO keyframes with the log by
    frame index, exposing a single timestamped pose stream for BA/fusion.

Format contract
---------------
Receiver log  (CSV, one header row):
    ts_ms, roll_deg, pitch_deg, yaw_deg, alt_m, vx, vy, vz
ESP32 camera meta (*_meta.json) already carries "fps"; we add frame numbers
0..N-1 (or the recorder's real per-frame wall stamps when "per_frame_ts" is
present -- they survive dropped frames, so they win over i/fps).  VO
keyframes from test_incr_pnp.py's *_traj.csv carry "frame".

Usage
-----
    from drone_sync import SyncTrajectory
    sc = SyncTrajectory("rc_log.csv", "seq_meta.json", "seq_traj.csv")
    print(sc.sync_points())   # [(t_sec, x, y, z, yaw_deg), ...]
"""

import argparse
import csv
import json

import numpy as np


def align_frames(log_ts, cam_ts):
    """Return index mapping between two sorted time domains (nearest).

    log_ts: 1-D array, monotonic receiver/log timestamps (seconds, any origin)
    cam_ts: 1-D array, monotonic per-frame camera timestamps (same unit)
    Returns (log_to_cam, cam_to_log) as arrays of indices (int32).
    """
    import numpy as np
    log_ts = np.asarray(log_ts, np.float64)
    cam_ts = np.asarray(cam_ts, np.float64)
    i = np.searchsorted(cam_ts, log_ts)
    i = np.clip(i, 0, len(cam_ts) - 1)
    lo = np.clip(i - 1, 0, len(cam_ts) - 1)
    d_hi = np.abs(cam_ts[i] - log_ts)
    d_lo = np.abs(cam_ts[lo] - log_ts)
    log_to_cam = np.where(d_lo <= d_hi, lo, i).astype(np.int32)

    j = np.searchsorted(log_ts, cam_ts)
    j = np.clip(j, 0, len(log_ts) - 1)
    jlo = np.clip(j - 1, 0, len(log_ts) - 1)
    d_hi = np.abs(log_ts[j] - cam_ts)
    d_lo = np.abs(log_ts[jlo] - cam_ts)
    cam_to_log = np.where(d_lo <= d_hi, jlo, j).astype(np.int32)
    return log_to_cam, cam_to_log


def read_receiver_log(path, ts_col="ts_ms", to_seconds=True):
    """Tolerant CSV loader. Returns (ts_sec, rows_dict_list)."""
    out = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out.append(row)
    if not out:
        raise ValueError("empty receiver log: %s" % path)
    ts = [float(r[ts_col]) for r in out]
    if to_seconds:
        unit = out[0].get(ts_col + "_unit", "ms")
        if "ms" in str(unit):
            ts = [t / 1000.0 for t in ts]
    return ts, out


class SyncTrajectory:
    """Merge receiver log + camera meta + VO trajectory into one pose stream."""

    def __init__(self, recv_log, cam_meta, vo_traj, fps=None):
        import numpy as np

        with open(cam_meta) as f:
            meta = json.load(f)
        self.fps = fps or float(meta.get("fps", 16.0))
        self.log_ts, self.log_rows = read_receiver_log(recv_log)
        self.log_ts = np.array(self.log_ts)

        with open(vo_traj) as f:
            self.traj = list(csv.DictReader(f))
        # keyframe camera frames are sorted in _traj.csv -> binary search
        self._kf_frames = np.array(
            [int(r["frame"]) for r in self.traj], np.int64) if self.traj \
            else np.empty(0, np.int64)

        # camera-frame clock: per-frame wall stamps when the recorder writes
        # them (these survive drops), else fall back to i/fps over the full
        # sequence length (HOLD0 + MOVE + HOLD1 summed)
        fr = meta.get("frames", {})
        self.n_cam = int(sum(int(v) for v in fr.values()) or
                          fr.get("MOVE", 0) or 0)
        pf = meta.get("per_frame_ts")
        if isinstance(pf, list) and len(pf) >= 2 and \
                all(isinstance(v, (int, float)) for v in pf):
            self.cam_ts = np.array(pf, np.float64)
        else:
            self.cam_ts = np.arange(self.n_cam, dtype=np.float64) / self.fps
        if self.cam_ts.ndim == 1 and len(self.cam_ts) > 1:
            # guard against a non-monotonic clock from an earlier buggy version
            m = np.maximum.accumulate(self.cam_ts)
            if not np.allclose(m, self.cam_ts):
                self.cam_ts = np.arange(len(self.cam_ts),
                                        dtype=np.float64) / self.fps

        self.log_to_cam, self.cam_to_log = align_frames(
            self.log_ts, self.cam_ts)

    def log_frame_for(self, log_row_idx):
        """Map a receiver-log line back to its camera frame index."""
        return int(self.log_to_cam[log_row_idx])

    def pose_for_cam_frame(self, cam_frame):
        """Nearest VO keyframe row for a camera frame (binary search)."""
        if self.traj is None or len(self.traj) == 0:
            return None
        i = int(np.searchsorted(self._kf_frames, cam_frame))
        i = min(max(i, 0), len(self._kf_frames) - 1)
        lo = max(i - 1, 0)
        d_hi = abs(int(self._kf_frames[i]) - cam_frame)
        d_lo = abs(int(self._kf_frames[lo]) - cam_frame)
        return self.traj[i if d_lo > d_hi else lo]

    def sync_points(self):
        """[(t_log_sec, x, y, z, roll, pitch, yaw)] fused at log cadence."""
        pts = []
        for i, r in enumerate(self.log_rows):
            row = self.pose_for_cam_frame(self.log_frame_for(i))
            if row is None:
                continue
            pts.append((
                self.log_ts[i],
                float(row["pre_x"]), float(row["pre_y"]), float(row["pre_z"]),
                float(r.get("roll_deg", 0.0)),
                float(r.get("pitch_deg", 0.0)),
                float(r.get("yaw_deg", 0.0)),
            ))
        return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recv_log", help="receiver/IMU CSV (ts_ms, roll_deg, ...)")
    ap.add_argument("cam_meta", help="record_clean_seq *_meta.json")
    ap.add_argument("vo_traj", help="test_incr_pnp *_traj.csv")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    sc = SyncTrajectory(a.recv_log, a.cam_meta, a.vo_traj)
    pts = sc.sync_points()
    print("synced %d points" % len(pts))
    for p in pts[:8] + pts[-8:]:
        print("\t%.3f sec  xyz(%.2f, %.2f, %.2f)  rpy(%.0f, %.0f, %.0f)"
              % p)
    if a.out:
        import numpy as np
        np.savetxt(a.out, np.asarray(pts, np.float64), delimiter=",",
                   header="t_sec,x,y,z,roll_deg,pitch_deg,yaw_deg")
        print("wrote", a.out)


if __name__ == "__main__":
    main()