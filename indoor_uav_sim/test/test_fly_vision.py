#!/usr/bin/env python3
"""Unit test for the fly-inspired (LPLC2) looming detector core.

Synthesizes small monocular frame sequences with numpy only (no OpenCV,
no Gazebo, no ROS) and checks that a looming (approaching) object drives the
looming score up while static scenes, lateral translation and receding objects
keep it low.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "obstacle_avoidance"))

from obstacle_avoidance.fly_vision import LoomingDetector  # noqa: E402

W, H = 640, 480
CX, CY = W / 2.0, H / 2.0


def blob_frame(radius, cx=CX, cy=CY, bg=0.08, fg=1.0):
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    profile = np.clip(1.0 - (dist / radius), 0.0, None) ** 2
    return (bg + profile * (fg - bg)) * 255.0


def run_sequence(frames):
    det = LoomingDetector()
    scores = []
    for frame in frames:
        scores.append(det.process(frame)["score"])
    return scores


def test_looming_raises_score():
    radii = np.linspace(25.0, 110.0, 45)
    frames = [blob_frame(r) for r in radii]
    scores = run_sequence(frames)
    peak = max(scores)
    approach = scores[1:16]
    assert peak > 0.5, f"looming peak score too low: {peak:.2f}"
    assert max(approach) > 0.4, f"approach window too quiet: {max(approach):.2f}"
    assert sum(approach) / len(approach) > 0.3, "approach should be sustained"

    det = LoomingDetector()
    azimuths = []
    for r in radii[:16]:
        azimuths.append(det.process(blob_frame(r))["azimuth"])
    assert abs(azimuths[-1]) < 0.3, (
        f"looming centroid azimuth off: {azimuths[-1]:.2f} rad"
    )
    print(f"  PASS: looming peak={peak:.2f} approach_mean="
          f"{sum(approach)/len(approach):.2f} az={azimuths[-1]:.3f} rad")


def test_static_stays_zero():
    frames = [blob_frame(60.0)] * 30
    scores = run_sequence(frames)
    peak = max(scores)
    assert peak < 0.1, f"static scene falsely triggered: peak={peak:.2f}"
    print(f"  PASS: static peak={peak:.2f}")


def test_translation_stays_low():
    det = LoomingDetector()
    scores = []
    for i in range(45):
        dx = i * 3.0
        scores.append(det.process(blob_frame(60.0, cx=CX + dx))["score"])
    peak = max(scores)
    assert peak < 0.35, f"lateral translation flagged as looming: peak={peak:.2f}"
    print(f"  PASS: translation peak={peak:.2f}")


def test_contraction_stays_low():
    radii = np.linspace(110.0, 25.0, 45)
    frame_list = [blob_frame(r) for r in radii]
    scores = run_sequence(frame_list)
    peak = max(scores)
    assert peak < 0.4, f"receding object flagged as looming: peak={peak:.2f}"
    print(f"  PASS: contraction peak={peak:.2f}")


if __name__ == "__main__":
    print("Fly-version (LPLC2) Looming Detector Unit Tests")
    print("=" * 44)
    test_looming_raises_score()
    test_static_stays_zero()
    test_translation_stays_low()
    test_contraction_stays_low()
    print("=" * 44)
    print("All tests passed!")