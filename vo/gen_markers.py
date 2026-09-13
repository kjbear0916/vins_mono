"""Regenerate the printed ArUco marker sheets for the indoor-GPS build.

Usage:
  python gen_markers.py                          # the default set (ids 0-5)
  python gen_markers.py --dict DICT_5X5_250 --ids 10,11,12 --size 800 --out markers/
"""
import argparse
import os

import cv2

DICTS = {n: cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, n))
         for n in dir(cv2.aruco) if n.startswith("DICT_")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dict", default="DICT_4X4_50")
    ap.add_argument("--ids", default="0,1,2,3,4,5")
    ap.add_argument("--size", type=int, default=400,
                    help="marker edge in px (printed size is set at print time)")
    ap.add_argument("--out", default=r"D:\Things\markers")
    a = ap.parse_args()

    if a.dict not in DICTS:
        raise SystemExit("unknown dict %r; choices: %s"
                         % (a.dict, ", ".join(sorted(DICTS))))
    os.makedirs(a.out, exist_ok=True)
    d = DICTS[a.dict]
    for mid in [int(x) for x in a.ids.split(",")]:
        img = cv2.aruco.generateImageMarker(d, mid, a.size)
        p = os.path.join(a.out, "marker_%d.png" % mid)
        cv2.imwrite(p, img)
        print("wrote", p)


if __name__ == "__main__":
    main()