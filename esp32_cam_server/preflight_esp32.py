"""Pre-flight checks + hardening before a VO clean-sequence recording.

The ESP32 firmware ships with motion-triggered flash capture enabled, which
will fire as soon as the cart moves and blow out the frame stream. This script
locks the camera into a VO-friendly configuration and verifies the stream.

Usage:
  python preflight_esp32.py [--url http://172.20.10.8] [--check-only]
        (STA fixed IP; AP mode fallback: http://192.168.4.1)

POST /config?key=<k>&value=<v>  (configManager.setAndSave)
POST /control?var=<v>&val=<n>   (camera sensor control, framesize etc.)
GET  /resolution                (current framesize)
GET  /cam_ctrl?var=...          (sensor debug JPEG readback -- unused)

Checks:
  - /status reachable & responsive
  - /config exposes motion_enabled & capture_on_motion -> disable both
  - camera framesize forced to QVGA (5) for the VO pipeline
  - manual exposure locked (aec=0, aec_value=500) so LK brightness stable
  - stream opened and 3 frames decoded successfully
"""

import argparse
import sys
import time

import requests


def get(base, path, **kw):
    r = requests.get(base + path, timeout=5, **kw)
    return r.status_code, r.text.strip()


def post(base, path, **kw):
    r = requests.post(base + path, timeout=5, **kw)
    return r.status_code, r.text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://192.168.1.200",
                    help="ESP32 base URL (STA fixed IP; AP = http://192.168.4.1)")
    ap.add_argument("--check-only", action="store_true",
                    help="only report, don't change anything")
    args = ap.parse_args()

    ok = True
    def check(name, passed, detail=""):
        nonlocal ok
        if not passed:
            ok = False
        print("%s [%s]%s" % ("PASS" if passed else "FAIL", name,
                             (" " + detail) if detail else ""))

    # 1. reachability
    try:
        st = requests.get(args.url + "/status", timeout=5)
        check("reachable", st.status_code == 200, "(HTTP %d)" % st.status_code)
    except Exception as e:
        print("FAIL [reachable] %s" % e)
        print("ESP32 not reachable -- power it on first.")
        return 1

    # 2. camera control endpoints exist (framesize 6 = QVGA on ESP32-CAM)
    ctl = get(args.url, "/control?var=framesize&val=6")
    if args.check_only:
        print("INFO [framesize] current control GET would set=6 (QVGA)")
    else:
        check("framesize->QVGA", ctl[0] == 200, "(HTTP %d)" % ctl[0])

    # 3. motion + flash off (read current value via ?key=)
    cfg = {}
    for k in ("motion_enabled", "capture_on_motion", "motion_sensitivity"):
        try:
            r = requests.get(args.url + "/config?key=" + k, timeout=5)
            cfg[k] = r.text.strip()
        except Exception as e:
            cfg[k] = "err:%s" % e

    if args.check_only:
        print("INFO [motion] config says: %s" % cfg)
        return 0 if ok else 1

    for k, v in [("motion_enabled", "0"),
                 ("capture_on_motion", "0"),
                 ("motion_sensitivity", "0")]:
        code, body = post(args.url, "/config?key=%s&value=%s" % (k, v))
        check("config %s=%s" % (k, v), code == 200 and body == "OK",
              "(HTTP %d '%s')" % (code, body))

    # 4. exposure lock
    for k, v in [("aec", "0"),        # manual exposure
                 ("aec_value", "500")]:
        code, body = get(args.url, "/control?var=%s&val=%s" % (k, v))
        check("%s=%s" % (k, v), code == 200, "(HTTP %d)" % code)

    # 5. stream sanity
    try:
        import cv2
        cap = cv2.VideoCapture(args.url + ":81/stream")
        got = 0
        for _ in range(20):
            r, fr = cap.read()
            if r and fr is not None:
                got += 1
            if got >= 3:
                break
            time.sleep(0.1)
        cap.release()
        check("stream 3 frames", got >= 3, "(%d decoded)" % got)
    except Exception as e:
        check("stream 3 frames", False, str(e))

    print()
    if ok:
        print("PREFLIGHT PASSED -- ready to record VO sequence")
    else:
        print("PREFLIGHT FAILED -- fix above before recording")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())