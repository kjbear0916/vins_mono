"""MJPEG replay test: capture the synthetic stream bytes, then replay them
through the exact live-reader parser and the full detection chain, offline.

Proves, without ESP32 or any network round trip:
  * the multipart boundary parser (mjpeg_frames) produces the right frames,
  * imdecode + find_board(SB) + canonical_corners + REQCollector run on the
    streamed bitstream -- the same path the live HTTP source takes,
  * the stream actually satisfies the REQ panel (all green -> would auto-save).

Also separates decode+detect throughput from network: the wall-clock rate of
the capture goes through requests, the replay rate does not.

Usage:
  python vo/mjpeg_replay_test.py
"""
import argparse
import io
import os
import sys
import tempfile
import threading
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import calibrate_guided as cg
import gen_guided_pose_set as gp
import synth_mjpeg_server as srv
import video_source
from calibrate_guided import (classify_detection, find_board, REQCollector)


def main():
    tmp = tempfile.mkdtemp(prefix="mjpeg_replay_")
    stream_file = os.path.join(tmp, "stream.mjpeg")

    # -- serve the guided pose set, not the fallback make_poses --------------
    K = np.array([[474.0, 0, 160], [0, 474.0, 120], [0, 0, 1]])
    dist = np.array([-0.18, 0.05, 0, 0, 0])
    poses = gp.build(K, dist, 25.0, 24.0, 15.0, 8.0, 60.0, 30, noise=3.0)
    a = argparse.Namespace(port=0, fps=12.0, fx=474.0, fy=None, cx=160.0,
                           cy=120.0, k1=-0.18, k2=0.05, p1=0.0, p2=0.0,
                           k3=0.0, noise=3.0, seed=7, poses=poses)
    srv_obj = srv.ThreadingHTTPServer(("127.0.0.1", 0), srv.make_handler(a))
    port = srv_obj.server_address[1]
    t = threading.Thread(target=srv_obj.serve_forever, daemon=True)
    t.start()

    # -- capture the real bytes the reader would receive ----------------------
    import requests
    url = "http://127.0.0.1:%d/stream" % port
    really = {"n": 0}
    t0 = time.time()
    try:
        with requests.get(url, stream=True, timeout=10) as r:
            with open(stream_file, "wb") as f:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=16384):
                    f.write(chunk)
                    really["n"] += 1
                    if really["n"] >= 240:
                        break
    except requests.exceptions.ConnectionError as e:
        print("capture failed:", e)
        return 2
    cap_elapsed = time.time() - t0
    srv_obj.shutdown()

    size = os.path.getsize(stream_file)
    print("captured %d chunks, %.1f KB in %.2fs (network path %d B/s)"
          % (really["n"], size / 1024.0, cap_elapsed, size / cap_elapsed))

    # -- replay offline through the identical parser ---------------------------
    with open(stream_file, "rb") as f:
        raw = f.read()
    buf = bytearray(raw)
    jpegs = list(video_source.mjpeg_frames(buf))
    print("parser produced %d JPEG frames from %.1f KB"
          % (len(jpegs), size / 1024.0))
    if not jpegs:
        print("PARSER BROKEN: no frames")
        return 1

    # -- run the same chain the live HTTP source + guided tool would -----------
    obj = np.zeros((20, 3), np.float32)
    obj[:, :2] = np.mgrid[0:5, 0:4].T.reshape(-1, 2) * 25.0
    collector = REQCollector(obj, 30, 2, 15.0)
    decoded = detected = 0
    t0 = time.time()
    rejects = {"lattice": 0, "off-frame": 0, "bad-size": 0}
    for jpeg in jpegs:
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        decoded += 1
        found, cc, how = find_board(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY),
                                    (5, 4))
        if not found or not how.startswith("sb"):
            continue
        detected += 1
        d = classify_detection(cc, (5, 4), 25.0, 8.0, 60.0)
        rej = d.get("reject")
        if rej:
            rejects[rej] = rejects.get(rej, 0) + 1
            continue
        collector.add(d)
        if collector.done():
            break
    elapsed = time.time() - t0
    miss = collector.missing()

    print("replay: decoded=%d  sb-detect=%d  rejects=%s  unique-samples=%d"
          % (decoded, detected, rejects, collector.n_add))
    print("decode+detect throughput: %.1f fps offline" % (decoded / elapsed))
    print("REQ: %s" % ("MISSING: " + "; ".join(miss) if miss else "all green"))
    if collector.n_add >= 30 and not miss:
        print("OFFLINE MJPEG REPLAY PASS: parser + detector chain verified")
        return 0
    print("OFFLINE REPLAY FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())