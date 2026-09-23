import argparse
import re
import subprocess
import sys
import time

import requests

DEFAULT_URL = "http://192.168.4.1"
AP_SSID = "RatMonitor_Setup"


def sh(*cmd):
    return subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def current_ssid():
    out = sh("netsh", "wlan", "show", "interfaces").stdout
    m = re.search(r"SSID\s+:\s+(.+)", out)
    return m.group(1).strip() if m else None


def connect_ap(timeout_secs=40):
    t0 = time.time()
    while time.time() - t0 < timeout_secs:
        ssid = current_ssid()
        if ssid == AP_SSID:
            return True
        if ssid is None or ssid != AP_SSID:
            sh("netsh", "wlan", "connect", "name=" + AP_SSID, "ssid=" + AP_SSID)
        time.sleep(3)
    return current_ssid() == AP_SSID


def renew_dhcp(timeout_secs=25):
    sh("ipconfig", "/release", "Wi-Fi")
    time.sleep(2)
    t0 = time.time()
    while time.time() - t0 < timeout_secs:
        sh("ipconfig", "/renew", "Wi-Fi")
        time.sleep(2)
        ip = re.search(r"192\.168\.4\.\d+", sh("ipconfig").stdout)
        if ip:
            return ip.group(0)
    return None


def wait_http(url, timeout_secs=90):
    t0 = time.time()
    while time.time() - t0 < timeout_secs:
        try:
            r = requests.get(url + "/status", timeout=3)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(3)
    return False


def main():
    p = argparse.ArgumentParser(description="Connect PC to ESP32 AP and wait for its HTTP server (outdoor AP mode).")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--connect-timeout", type=int, default=40)
    p.add_argument("--boot-timeout", type=int, default=90)
    a = p.parse_args()

    print(f"[1/3] 切到 {AP_SSID} ...")
    if not connect_ap(a.connect_timeout):
        print("FAIL: 連不上 ESP32 AP(確認它已開機、在 5 公尺內)")
        sys.exit(1)

    print(f"[2/3] 重新取 DHCP IP ...")
    ip = renew_dhcp()
    if not ip:
        print("FAIL: 沒拿到 192.168.4.x 的 IP")
        sys.exit(1)
    print(f"      拿到 IP = {ip}")

    print(f"[3/3] 等 ESP32 HTTP server 就緒(開機約 15-20 秒)...")
    if wait_http(a.url, a.boot_timeout):
        print(f"PASS: {a.url} 已通,可以錄影了")
        sys.exit(0)
    print("FAIL: HTTP server 一直沒回應——需要看開機 Serial log 找卡點")
    sys.exit(1)


if __name__ == "__main__":
    main()