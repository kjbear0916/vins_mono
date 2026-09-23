import sys
import numpy as np

npz_path = "/tmp/egm96_extract/egm96/data/egm96-5.npz"
out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/egm96-5.pgm"
axis_order = sys.argv[2] if len(sys.argv) > 2 else "01"

a = np.load(npz_path)
d2 = a["undulation_d2"].astype(np.int64)
lat = a["latitudes"]
lon = a["longitudes"]

if axis_order == "01":
    H_cm = np.cumsum(np.cumsum(d2, axis=0), axis=1)
else:
    H_cm = np.cumsum(np.cumsum(d2, axis=1), axis=0)

def bilinear(latv, lonv):
    li = np.searchsorted(lat, latv) - 1
    lo = np.searchsorted(lon, lonv) - 1
    li = min(max(li, 0), lat.shape[0] - 2)
    lo = min(max(lo, 0), lon.shape[0] - 2)
    wl = (latv - lat[li]) / (lat[li + 1] - lat[li])
    wo = (lonv - lon[lo]) / (lon[lo + 1] - lon[lo])
    v00 = H_cm[li, lo]
    v01 = H_cm[li, lo + 1]
    v10 = H_cm[li + 1, lo]
    v11 = H_cm[li + 1, lo + 1]
    return (v00 * (1 - wl) * (1 - wo) + v01 * (1 - wl) * wo +
            v10 * wl * (1 - wo) + v11 * wl * wo) / 100.0

for pt in [(48.14, 11.58), (40.7, -73.9), (0.0, 0.0), (60.0, 100.0)]:
    print("bilinear", pt, round(bilinear(*pt), 4))

H = H_cm / 100.0
print("H range m:", H.min(), H.max())

w, h = 4320, 2161
G = np.zeros((h, w), dtype=np.float64)
for j in range(h):
    m = 2160 - j
    for i in range(w):
        k = (i + 2160) % 4321
        G[j, i] = H[m, k]

offset, scale = -108.0, 0.003
pix = np.clip(np.rint((G - offset) / scale), 0, 65535).astype(np.uint16)
print("pix range:", pix.min(), pix.max())

header = (
    b"P5\n"
    b"# Geoid file in PGM format for the GeographicLib::Geoid class\n"
    b"# Description WGS84 EGM96, 5-minute grid\n"
    b"# URL http://earth-info.nga.mil/GandG/wgs84/gravitymod/egm96/egm96.html\n"
    b"# Offset -108\n"
    b"# Scale 0.003\n"
    b"# Origin 90.0 -180.0\n"
    b"# Interpolation cubic\n"
    b"# Format 1\n"
    b"4320 2161\n"
    b"65535\n"
)
body = pix.astype(">u2").tobytes()
with open(out_path, "wb") as f:
    f.write(header)
    f.write(body)
print("wrote", out_path, len(header) + len(body), "bytes")
print("header+data expected:", len(header) + w * h * 2)