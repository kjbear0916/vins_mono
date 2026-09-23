"""Show chessboard_screen.png fullscreen, 1 image px = 1 screen px.

DPI-aware so Windows never rescales the window; press ESC to exit.
"""
import ctypes

import cv2


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    set_dpi_aware()
    img = cv2.imread(r"D:\Things\vo\chessboard_screen.png")
    if img is None:
        print("run gen_screen_board.py first")
        return 1
    win = "board -- ESC to exit"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.resizeWindow(win, img.shape[1], img.shape[0])
    scale = 1.0
    while True:
        disp = cv2.resize(img, None, fx=scale, fy=scale,
                          interpolation=cv2.INTER_NEAREST)
        cv2.imshow(win, disp)
        key = cv2.waitKey(30) & 0xFF
        if key in (27, ord("q")):
            break
        if key == ord("-"):
            scale = max(0.25, scale / 1.25)
        if key == ord("+"):
            scale = min(4.0, scale * 1.25)
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())