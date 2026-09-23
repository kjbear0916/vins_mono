# -*- coding: utf-8 -*-
"""Generate a PRINTABLE chessboard for the QVGA calibration recordings.

The screen board (gen_screen_board.py) is only usable on a monitor; the
hardware phase D needs a physical board taped to cardboard/wall so the
ESP32-CAM can film it near/edge/far across all 5 frame zones.

Renders a 5x4 chessboard (6x5 cells) with squares of an EXACT physical size:
when printed at 100% scale (actual size) the square edge equals --sq-mm.
A 100 mm reference ruler is embedded below the board so the user can verify
the printer did not rescale the page.

Printing advice: enable "actual size / 100%" (do NOT crop or fit-to-page);
after printing, measure the ruler with a ruler -- if it reads 100 mm the
board squares are exactly --sq-mm and calibrate_guided.py can be fed
--square <sq-mm> directly.

Usage (default: A4 at 300 dpi, 25 mm squares, as in HARDWARE_PHASE_RUNBOOK D):
  python vo/gen_print_board.py --out vo/chessboard_print_A4_25mm.png

For a different square size or page:
  python vo/gen_print_board.py --sq-mm 22 --dpi 300 --pad-mm 30 \
      --out vo/chessboard_print_A4_22mm.png
"""
import argparse

import cv2
import numpy as np

PATTERN = (5, 4)    # inner corners (cols, rows) -> 6x5 cells
A4_W_MM, A4_H_MM = 210.0, 297.0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sq-mm", type=float, default=25.0,
                    help="square edge in mm at 100% print (default 25)")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--pad-mm", type=float, default=20.0,
                    help="white padding around the board, mm")
    ap.add_argument("--out", default=r"D:\Things\vo\chessboard_print_A4.png")
    a = ap.parse_args()

    ppmm = a.dpi / 25.4
    sq_px = int(round(a.sq_mm * ppmm))
    sq_mm = sq_px / ppmm
    cols, rows = PATTERN
    n_c, n_r = cols + 1, rows + 1
    board_px = (n_c * sq_px, n_r * sq_px)
    board_mm = (n_c * sq_mm, n_r * sq_mm)

    page_px = (int(round(A4_W_MM * ppmm)), int(round(A4_H_MM * ppmm)))
    canvas = np.full((page_px[1], page_px[0]), 255, np.uint8)

    bx, by = page_px[0] - board_px[0], page_px[1] - board_px[1]
    ox, oy = bx // 2, by // 2 - int(40 * ppmm)

    board = np.full((board_px[1], board_px[0]), 255, np.uint8)
    for r in range(n_r):
        for c in range(n_c):
            if (r + c) % 2 == 0:
                y0, x0 = r * sq_px, c * sq_px
                board[y0:y0 + sq_px, x0:x0 + sq_px] = 0
    canvas[oy:oy + board_px[1], ox:ox + board_px[0]] = board

    ruler_x = int(4 * ppmm)
    ruler_w = int(100 * ppmm)
    ruler_y = oy + board_px[1] + int(14 * ppmm)
    canvas[ruler_y, ruler_x:ruler_x + ruler_w] = 0
    for mm in range(0, 101, 5):
        x = ruler_x + int(mm * ppmm)
        h = int(8 * ppmm) if mm % 10 == 0 else int(4 * ppmm)
        canvas[ruler_y - h:ruler_y, x:x + 1] = 0
    cv2.putText(canvas, "100 mm (check this ruler = 100 mm)",
                (ruler_x, ruler_y + int(12 * ppmm)), cv2.FONT_HERSHEY_SIMPLEX,
                0.8 * a.dpi / 96.0, 0, 2)
    cv2.putText(canvas,
                f"chessboard %dx%d  sqb {sq_mm:.2f} mm  page {A4_W_MM:.0f}x{A4_H_MM:.0f} mm"
                % (n_c, n_r), (ruler_x, ruler_y + int(26 * ppmm)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6 * a.dpi / 96.0, 0, 2)

    ok = cv2.imwrite(a.out, canvas, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    if not ok:
        raise SystemExit("failed to write " + a.out)
    print("WROTE", a.out)
    print(f"board {board_mm[0]:.1f} x {board_mm[1]:.1f} mm  "
          f"({board_px[0]}x{board_px[1]} px)  sq {sq_mm:.2f} mm")
    print("print at 100%%/actual size; check the 100 mm ruler; then run:")
    print(f"  calibrate_guided.py --square {sq_mm:.2f}")


if __name__ == "__main__":
    main()