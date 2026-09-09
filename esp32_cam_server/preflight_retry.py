import subprocess
import sys
import time

import requests


def shell(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout + r.stderr


def current_ssid():
    out = shell(["netsh", "wlan", "show", "interfaces"])
    for line in out.splitlines():
        s = line.strip()
        if s.lower().startswith("ssid"):
            return s.split(":", 1)[1].strip()
    return ""


def run_preflight(base="http://192.168.4.1"):
    print("-- preflight --")
    r = subprocess.run([sys.executable, "preflight_esp32.py", "--url", base],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout)
    if r.stderr:
        print(r.stderr)
    return r.returncode == 0


def main():
    target = "RatMonitor_Setup"
    for attempt in range(8):
        print(f"[attempt {attempt+1}] connect to {target} ...")
        shell(["netsh", "wlan", "connect", "name=" + target, "ssid=" + target])
        for _ in range(12):
            time.sleep(2)
            ssid = current_ssid()
            if ssid == target:
                ok = run_preflight()
                if ok:
                    print("PREFLIGHT PASSED")
                    return 0
                break
        print(f"  -> current SSID={current_ssid()!r}, retrying")
    print("PREFLIGHT FAILED after retries")
    return 1


if __name__ == "__main__":
    sys.exit(main())