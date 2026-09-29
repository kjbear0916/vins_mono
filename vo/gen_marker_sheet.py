# -*- coding: utf-8 -*-
"""Generate printable A4 ArUco marker sheets for the indoor-GPS build.

runbook step A prints marker_00..05 (DICT_4X4_50) with an EXACT 15 cm black
frame. The A4 page is laid out at 300 dpi (2480 x 3508 px), so a full-bleed
A4 hardcopy maps page width to 210 mm; a marker whose black frame must be
150 mm is therefore round(150 * 300 / 25.4) = 1772 px.

cv2.aruco.generateImageMarker() emits a marker whose black outer frame runs
edge-to-edge (no white margin); the solver measures the outer edge of that
black frame, so the page pixel number IS the frame size. The white A4 page
itself provides the surround that the detector needs, so markers are placed
natively (never cropped - cropping native output cuts into the data cells and
kills decoding). Every page also carries a real 100 mm ruler
(round(100 * 300 / 25.4) = 1181 px) to verify the printer's scaling:
if the ruler reads 100 mm the frames are exactly 15.0 cm; if the printer
shrinks to its printable area the ruler reads proportionally less and the
measured frame must be fed to localise_video.py --marker-m /
tests/test_marker_detect.py --marker-length.

Produced:
  * marker_00..05_A4.png     : one marker per A4 page, black frame exactly
                               150.0 mm when printed full-bleed to A4;
  * marker_sheet_6up_A4.png  : 2x3 A4 dry-run sheet, 60.0 mm black frames.

Usage:
  python vo/gen_marker_sheet.py --out markers/printable/
"""
import argparse
import os

import cv2
import numpy as np

DICT = getattr(cv2.aruco, "DICT_4X4_50")
IDS = [0, 1, 2, 3, 4, 5]
PPMM = 300.0 / 25.4                      # px per mm (A4 at 300 dpi)
SQ_150MM_PX = int(round(150 * PPMM))     # 1772 px == 150 mm on A4
SIXUP_60MM_PX = int(round(60 * PPMM))    # 709 px  == 60 mm on A4
BAR_100MM_PX = int(round(100 * PPMM))    # 1181 px == 100 mm on A4


def native_marker(mid, edge_px):
    """Full-bleed native marker: black outer frame edge == edge_px (never crop)."""
    d = cv2.aruco.getPredefinedDictionary(DICT)
    return cv2.aruco.generateImageMarker(d, mid, edge_px)


def ruler_on(canvas, x0, y0, length_px, label):
    cv2.line(canvas, (x0, y0), (x0 + length_px - 1, y0), 0, 2)
    for mm in range(0, 101, 10):
        x = x0 + int(mm * length_px / 100)
        h = int(11 * PPMM) if mm % 20 == 0 else int(6 * PPMM)
        cv2.line(canvas, (x, y0 - h), (x, y0), 0, 2)
    cv2.putText(canvas, label, (x0, y0 - int(16 * PPMM)),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 2)


def page(mid):
    W, H = int(round(210 * PPMM)), int(round(297 * PPMM))
    canvas = np.full((H, W), 255, np.uint8)
    img = native_marker(mid, SQ_150MM_PX)
    e = img.shape[0]
    x0 = (W - e) // 2
    label_h = int(8 * PPMM) + int(18 * PPMM)
    ruler_h = int(48 * PPMM)
    y_top = (H - (e + label_h + ruler_h)) // 2
    canvas[y_top:y_top + e, x0:x0 + e] = img
    label_y = y_top + e + int(8 * PPMM)
    cv2.putText(canvas, "id=%d  black frame = 15.0 cm on A4" % mid,
                (x0, label_y + int(18 * PPMM)), cv2.FONT_HERSHEY_SIMPLEX,
                1.4, 0, 2)
    ruler_on(canvas, int(10 * PPMM), label_y + int(48 * PPMM),
             BAR_100MM_PX, "100 mm (check this ruler)")
    return canvas


def sheet_6up(cell_px=SIXUP_60MM_PX, pad_px=52):
    W, H = int(round(210 * PPMM)), int(round(297 * PPMM))
    canvas = np.full((H, W), 255, np.uint8)
    ncol, nrow = 2, 3
    pitch_w = (W - (ncol + 1) * pad_px) // ncol
    pitch_h = (H - (nrow + 1) * pad_px) // nrow
    cell = min(cell_px, pitch_w - 20, pitch_h - 64)
    for i, mid in enumerate(IDS):
        r, c = divmod(i, ncol)
        img = native_marker(mid, cell)
        x0 = pad_px + c * (pitch_w + pad_px) + (pitch_w - cell) // 2
        y0 = pad_px + r * (pitch_h + pad_px) + (pitch_h - cell) // 2
        canvas[y0:y0 + cell, x0:x0 + cell] = img
        cv2.putText(canvas, "id=%d %d mm" % (mid, int(cell / PPMM)),
                    (x0, y0 + cell + int(20 * PPMM)), cv2.FONT_HERSHEY_SIMPLEX,
                    1.1, 0, 2)
    return canvas


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=r"D:\Things\markers\printable")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    det = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(DICT),
        cv2.aruco.DetectorParameters())
    for mid in IDS:
        cv2.imwrite(os.path.join(a.out, "marker_%02d_A4.png" % mid),
                    page(mid), [cv2.IMWRITE_PNG_COMPRESSION, 9])
    p6 = os.path.join(a.out, "marker_sheet_6up_A4.png")
    cv2.imwrite(p6, sheet_6up(), [cv2.IMWRITE_PNG_COMPRESSION, 9])
    print("WROTE 6 single pages + 6-up sheet in %s" % a.out)
    print("black frames: 150.0 mm (single), 60.0 mm (6-up) at full-bleed A4")
    print("print setting: Fit-to-A4 / scale to paper (no %% cropping)")
    g = cv2.imread(os.path.join(a.out, "marker_00_A4.png"), 0)
    ids = det.detectMarkers(g)[1]
    n = sorted(int(x) for x in np.ravel(ids)) if ids is not None and len(ids) else []
    print("self-check detect marker_00_A4:", n if n else "FAIL (no id)")


if __name__ == "__main__":
    main()