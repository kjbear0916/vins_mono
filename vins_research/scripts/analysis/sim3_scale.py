#!/usr/bin/env python3
"""Sim3 (7-DoF Umeyama) scale between a GT and an estimated trajectory.

Prints the scale factor `s` and the path-length ratio V/G so a run's monocular
scale can be attributed without invoking evo_ape by hand.

Usage:
    sim3_scale.py <gt.tum> <est.txt|est.tum>
"""
import sys
import numpy as np
from evo.tools import file_interface
from evo.core import sync


def path_len(xyz):
    return float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).sum())


def main():
    gt = file_interface.read_tum_trajectory_file(sys.argv[1])
    est = file_interface.read_tum_trajectory_file(sys.argv[2])
    gt, est = sync.associate_trajectories(gt, est)
    gl = path_len(gt.positions_xyz)
    el = path_len(est.positions_xyz)
    _r, _t, s = est.align(gt, correct_scale=True, correct_only_scale=False)
    ratio = el / gl if gl else float("nan")
    print("SIM3 scale=%.4f path_ratio_V/G=%.4f" % (s, ratio))
    return 0


if __name__ == "__main__":
    sys.exit(main())
