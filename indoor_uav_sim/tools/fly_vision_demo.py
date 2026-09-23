#!/usr/bin/env python3
"""Fly-inspired (LPLC2) looming detector demo.

Synthesizes monocular frame sequences and plots the detector's score /
azimuth traces so the looming response can be inspected without Gazebo.
Saves artifacts/fly_vision_demo.png.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "obstacle_avoidance"))

from obstacle_avoidance.fly_vision import LoomingDetector  # noqa: E402

W, H = 640, 480
CX, CY = W / 2.0, H / 2.0
HFOV = 80.0 * np.pi / 180.0


def blob_frame(radius, cx=CX, cy=CY, bg=0.08, fg=1.0):
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    profile = np.clip(1.0 - (dist / radius), 0.0, None) ** 2
    return (bg + profile * (fg - bg)) * 255.0


def format_azimuth(az):
    return f"{np.degrees(az):+6.1f} deg"


def collect(frames, hfov=HFOV):
    det = LoomingDetector()
    scores, azimuths = [], []
    for frame in frames:
        report = det.process(frame, hfov=hfov)
        scores.append(report["score"])
        azimuths.append(report["azimuth"])
    return np.array(scores), np.array(azimuths)


frames_loom = [blob_frame(r) for r in np.linspace(25.0, 110.0, 45)]
frames_static = [blob_frame(60.0)] * 30
frames_trans = [blob_frame(60.0, cx=CX + i * 3.0) for i in range(45)]
frames_contr = [blob_frame(r) for r in np.linspace(110.0, 25.0, 45)]
frames_offcenter = [blob_frame(r, cx=CX + 130.0) for r in np.linspace(25.0, 90.0, 35)]

loom_s, loom_a = collect(frames_loom)
static_s, _ = collect(frames_static)
trans_s, _ = collect(frames_trans)
contr_s, _ = collect(frames_contr)
off_s, off_a = collect(frames_offcenter)

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))

ax = axes[0]
ax.plot(loom_s, label="looming (approach)")
ax.plot(static_s, label="static")
ax.plot(trans_s, label="lateral translation")
ax.plot(contr_s, label="receding")
ax.axhline(0.35, color="tab:red", ls="--", lw=1, label="avoider threshold")
ax.set_title("Looming score by scene type")
ax.set_xlabel("frame")
ax.set_ylabel("score")
ax.legend()
ax.grid(alpha=0.3)

ax = axes[1]
ax.plot(off_a)
ax.axhline(0.0, color="gray", ls=":", lw=1)
ax.set_title("Off-center looming: threat azimuth")
ax.set_xlabel("frame")
ax.set_ylabel("azimuth (rad)")
ax.grid(alpha=0.3)
ax.annotate(
    f"final = {format_azimuth(off_a[-1])}",
    xy=(0.65, 0.1),
    xycoords="axes fraction",
    fontsize=9,
)

ax = axes[2]
ax.plot(loom_s, label="looming approach score")
ax.plot(off_s, label="off-center looming score")
ax.fill_between(
    range(len(loom_s)), 0, loom_s, alpha=0.15, color="tab:blue"
)
ax.set_title("Score build-up (escape cue)")
ax.set_xlabel("frame")
ax.set_ylabel("score")
ax.legend()
ax.grid(alpha=0.3)

fig.tight_layout()
out = ROOT / "artifacts" / "fly_vision_demo.png"
out.parent.mkdir(exist_ok=True)
fig.savefig(out, dpi=130)
print(f"saved: {out}")

print(f"looming peak={loom_s.max():.2f}   static peak={static_s.max():.2f}")
print(f"translation peak={trans_s.max():.2f}   receding peak={contr_s.max():.2f}")
print(f"off-center looming final azimuth={format_azimuth(off_a[-1])}  "
      f"(expected ~+18.6 deg for cx=+130px)")