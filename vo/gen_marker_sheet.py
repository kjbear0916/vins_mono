# -*- coding: utf-8 -*-
"""Generate printable A4 ArUco marker sheets for the indoor-GPS build.

runbook step A prints marker_00..05 (DICT_4X4_50) at ~15 cm edge. This
script produces what the printer needs:

  * one A4 page per marker: marker centered with a 15 cm edge when printed
    at 100% (actual size) -- the recommended size for step G, bigger =
    more pixels on camera = higher localisation accuracy;
  * a 6-up A4 sheet (2x3 grid) with a smaller edge for fast pre-deploy
    dry-run scanning (step C).

Every page carries a 50 px id label under the marker and a 100 mm scale
bar so print scaling can be verified like the chessboard ruler.

Usage:
  python vo/gen_marker_sheet.py --out markers/printable/

After printing 100% check any 100 mm bar == 100 mm, then measure the real
marker edge and feed that value to localise_video.py --marker-m and
tests/test_marker_detect.py --marker-length.
"""
import argparse
import os

import cv2
import numpy as np

DICT = getattr(cv2.aruco, "DICT_4X4_50")
IDS = [0, 1, 2, 3, 4, 5]
SQ_15CM_PX = 600          # marker_XX.png size -> 15 cm at the source DPI
LABEL_PX = 50
BAR_100MM_PX = 400


def marker_img(mid, edge_px):
    d = cv2.aruco.getPredefinedDictionary(DICT)
    return cv2.aruco.generateImageMarker(d, mid, edge_px)


def page(single_id=None, edge_px=SQ_15CM_PX):
    """A4 (300 dpi) with one centered marker of the given edge in mm-as-px."""
    A4 = (int(210.0 / 25.4 * 300), int(297.0 / 25.4 * 300))
    W, H = A4
    canvas = np.full((H, W), 255, np.uint8)
    if single_id is not None:
        img = marker_img(single_id, edge_px)
        x0 = (W - edge_px) // 2
        y0 = (H - edge_px) // 2 - LABEL_PX
        canvas[y0:y0 + edge_px, x0:x0 + edge_px] = img
        cv2.putText(canvas, "id=%d  edge 15 cm at 100%%" % single_id,
                    (x0, y0 + edge_px + LABEL_PX - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, 0, 2)
    # scale bar
    by = H - 60
    bx0 = (W - BAR_100MM_PX) // 2
    canvas[by, bx0:bx0 + BAR_100MM_PX] = 0
    for mm in range(0, 101, 10):
        x = bx0 + int(mm * BAR_100MM_PX / 100)
        canvas[by - 30:by, x:x + 2] = 0
    cv2.putText(canvas, "100 mm", (bx0, by - 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, 0, 2)
    return canvas


def sheet_6up(cell_px=380, pad_px=40):
    A4 = (int(210.0 / 25.4 * 300), int(297.0 / 25.4 * 300))
    W, H = A4
    canvas = np.full((H, W), 255, np.uint8)
    ncol, nrow = 2, 3
    cw = (W - (ncol + 1) * pad_px) // ncol
    ch = (H - (nrow + 1) * pad_px) // nrow
    cell = min(cw, ch)
    for i, mid in enumerate(IDS):
        r, c = divmod(i, ncol)
        img = marker_img(mid, cell)
        x0 = pad_px + c * (cell + pad_px)
        y0 = pad_px + r * (cell + pad_px)
        canvas[y0:y0 + cell, x0:x0 + cell] = img
        cv2.putText(canvas, "id=%d" % mid, (x0, y0 + cell + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, 0, 2)
    return canvas


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=r"D:\Things\markers\printable")
    ap.add_argument("--edge-px", type=int, default=SQ_15CM_PX)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    n = 0
    for mid in IDS:
        cv2.imwrite(os.path.join(a.out, "marker_%02d_A4.png" % mid),
                    page(mid, a.edge_px), [cv2.IMWRITE_PNG_COMPRESSION, 9])
        n += 1
    p6 = os.path.join(a.out, "marker_sheet_6up_A4.png")
    cv2.imwrite(p6, sheet_6up(), [cv2.IMWRITE_PNG_COMPRESSION, 9])
    print("WROTE %d single pages + 6-up sheet in %s" % (n, a.out))


if __name__ == "__main__":
    main()