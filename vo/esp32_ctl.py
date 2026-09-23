"""one-shot ESP32 camera /control tweaker: python esp32_ctl.py led_intensity=0 quality=30

Uses GET /control on both the web (80) and stream (81) servers and prints
whatever each returns so the caller can see the result without a browser.
"""
import sys

import requests


def main():
    pairs = [a.split("=", 1) for a in sys.argv[1:]]
    pairs = [(k, v) for k, v in pairs if k and v]
    if not pairs:
        print("usage: python esp32_ctl.py <var>=<val> [<var>=<val>...]")
        return 1
    for port in (80, 81):
        for var, val in pairs:
            try:
                r = requests.get(
                    f"http://192.168.4.1:{port}/control",
                    params={"var": var, "val": val}, timeout=5)
                print(f":{port} {var}={val} -> {r.status_code} {r.text.strip()!r}")
            except Exception as e:
                print(f":{port} {var}={val} -> ERR {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())