"""Detect the real monitor pixel pitch and generate an exact-size chessboard.

Windows reports the physical screen size via GetDeviceCaps on laptops with
proper EDID/driver data, so each screen pixel maps to a known mm and a
displayed chessboard has a deterministic square side -- no printer needed.

If the driver-reported size is wrong (or --width-mm is given), measure the
screen's visible width with a ruler and pass it:

    python gen_screen_board.py --width-mm 344

Prints the square side in mm to feed calibrate_guided.py --square.
"""
import argparse
import ctypes

import cv2
import numpy as np

TARGET_SQ_MM = 30.0      # desired square side
PATTERN = (5, 4)         # inner corners (cols, rows)


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # system DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def monitor_res():
    set_dpi_aware()
    hdc = ctypes.windll.user32.GetDC(0)
    w_px = ctypes.windll.gdi32.GetDeviceCaps(hdc, 118)  # HORZRES
    h_px = ctypes.windll.gdi32.GetDeviceCaps(hdc, 117)  # VERTRES
    ctypes.windll.user32.ReleaseDC(0, hdc)
    return w_px, h_px


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--width-mm", type=float, default=None,
                    help="measured physical screen width in mm "
                         "(overrides driver-reported size)")
    a = ap.parse_args()

    w_px, h_px = monitor_res()
    if a.width_mm:
        w_mm = a.width_mm
        src = "measured"
    else:
        hdc = ctypes.windll.user32.GetDC(0)
        w_mm = ctypes.windll.gdi32.GetDeviceCaps(hdc, 4)   # HORZSIZE
        ctypes.windll.user32.ReleaseDC(0, hdc)
        src = "driver"
    pitch = w_mm / w_px
    print(f"screen {w_px}x{h_px}  width {w_mm:.0f} mm ({src})  "
          f"pixel pitch {pitch:.4f} mm/px")
    sane = (800 <= w_px <= 5120 and 0.08 <= pitch <= 0.35)
    if not sane:
        print("ERROR: pixel pitch looks wrong. Measure screen width with a "
              "ruler and rerun with --width-mm <mm>.")
        return 1

    sq_px = int(round(TARGET_SQ_MM / pitch))
    sq_mm = sq_px * pitch
    cols, rows = PATTERN
    n_c, n_r = cols + 1, rows + 1
    margin = sq_px // 2
    W = n_c * sq_px + 2 * margin
    H = n_r * sq_px + 2 * margin
    img = np.zeros((H, W, 3), np.uint8)  # black frame around the board
    for r in range(n_r):
        for c in range(n_c):
            if (r + c) % 2 == 0:
                y0 = margin + r * sq_px
                x0 = margin + c * sq_px
                img[y0:y0 + sq_px, x0:x0 + sq_px] = 255
    out = r"D:\Things\vo\chessboard_screen.png"
    cv2.imwrite(out, img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    print(f"square = {sq_px} px  =>> {sq_mm:.2f} mm  (desired {TARGET_SQ_MM})")
    print(f"board {n_c*sq_mm:.0f} x {n_r*sq_mm:.0f} mm")
    print(f"calibrate with:  python calibrate_guided.py "
          f"--square {sq_mm:.2f} --out D:\\Things\\vo\\calibration_esp32_qvga_v2.npz")
    print("fullscreen (1 img px = 1 screen px):  python show_board_fullscreen.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())