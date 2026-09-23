"""
產生假資料,供 3D 視覺化 demo 先行測試呈現效果。
之後有真機 marker 系統的實際輸出後,直接用同樣格式替換即可。

輸出:
- fake_traj.json : 完整資料(純VO軌跡 + Marker校正後軌跡 + 房間 + markers)
- data_embed.js   : window.__VO_DATA__ JS 片段(供 node/瀏覽器直接讀)
- room_3d_demo.html : 自動把這份資料內嵌進 HTML 的資料塊(// __DATA_BEGIN__ ~ // __DATA_END__)

資料欄位契約(與 room_3d_demo.html 完全對應):
  room: {width, depth, height}
  markers: [{id, x, y, z}]            # 牆面上的絕對座標
  waypoints: [{label, x, y, z}]       # 搜救航點(SAR-1~3 / 起降區)
  ground_truth:       [[x,y,z], ...]
  vo_trajectory:      [[x,y,z], ...]  # 純VO,隨時間累積漂移
  corrected_trajectory: [[x,y,z], ...]# 經過 marker 校正,較貼近真值

最終校准:純VO末端誤差 ~0.80m,校正後末端誤差 ~0.10m(呈現漂移 vs 校正的對比)
"""

import json
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(HERE, "room_3d_demo.html")
JSON_PATH = os.path.join(HERE, "fake_traj.json")
JS_PATH = os.path.join(HERE, "data_embed.js")

np.random.seed(42)

# 模擬房間尺寸(公尺),對應一個約 4m x 3m x 2.5m 高的房間
ROOM = {"width": 4.0, "depth": 3.0, "height": 2.5}

# 模擬 6 個 marker 的絕對座標(牆面上,分散佈署)
markers = [
    {"id": 0, "x": 0.0, "y": 0.0, "z": 1.2},
    {"id": 1, "x": 4.0, "y": 0.0, "z": 1.2},
    {"id": 2, "x": 4.0, "y": 3.0, "z": 1.5},
    {"id": 3, "x": 0.0, "y": 3.0, "z": 0.9},
    {"id": 4, "x": 2.0, "y": 0.0, "z": 1.8},
    {"id": 5, "x": 2.0, "y": 3.0, "z": 1.0},
]

# 搜救航點:依序繞一圈(SAR-1 -> SAR-2 -> SAR-3 -> 起降區)
waypoints = [
    {"label": "SAR-1", "x": 3.5, "y": 0.5, "z": 1.0},
    {"label": "SAR-2", "x": 3.5, "y": 2.5, "z": 1.0},
    {"label": "SAR-3", "x": 0.5, "y": 2.5, "z": 1.0},
    {"label": "降落區", "x": 0.5, "y": 0.5, "z": 1.0},
]

# 模擬一條「真實路徑」:沿房間繞一圈的路徑,由幾個航點構成
route = [
    (0.5, 0.5, 1.0),
    (3.5, 0.5, 1.0),
    (3.5, 2.5, 1.0),
    (0.5, 2.5, 1.0),
    (0.5, 0.5, 1.0),
]

TARGET_VO_ERR = 0.80    # 純VO末端誤差目標
TARGET_CORR_ERR = 0.10  # 校正後末端誤差目標


def interpolate_path(waypoints, n_points):
    """在航點之間線性插值,產生平滑路徑"""
    waypoints = np.array(waypoints)
    seg_count = len(waypoints) - 1
    pts_per_seg = n_points // seg_count
    path = []
    for i in range(seg_count):
        p0, p1 = waypoints[i], waypoints[i + 1]
        for t in np.linspace(0, 1, pts_per_seg, endpoint=False):
            path.append(p0 + (p1 - p0) * t)
    path.append(waypoints[-1])
    return np.array(path)


n_frames = 200
ground_truth = interpolate_path(route, n_frames)
marker_positions_arr = np.array([[m["x"], m["y"], m["z"]] for m in markers])


def build_vo(gt):
    """純VO:系統性漂移(誤差隨距離累積)+ 隨機雜訊"""
    drift = np.zeros(3)
    drift_rate = np.array([0.004, 0.0028, 0.001])
    traj = []
    for i, g in enumerate(gt):
        drift = drift + drift_rate * (1 + 0.3 * np.sin(i * 0.05))
        traj.append(g + drift + np.random.normal(0, 0.01, 3))
    return np.array(traj)


def build_corrected(gt):
    """VO + Marker 校正:經過 marker 附近被拉回接近真值,其餘時間仍有小幅漂移"""
    residual_drift = np.zeros(3)
    drift_rate = np.array([0.004, 0.0028, 0.001]) * 0.35
    traj = []
    for i, g in enumerate(gt):
        dists = np.linalg.norm(marker_positions_arr - g, axis=1)
        if np.min(dists) < 0.9:  # 接近 marker(約0.9m內視為看得到)就大幅拉回
            residual_drift *= 0.15
        else:
            residual_drift = residual_drift + drift_rate
        traj.append(g + residual_drift + np.random.normal(0, 0.015, 3))
    return np.array(traj)


def normalize_error(traj, gt, target):
    """把軌跡相對真值的偏移等比縮放,使末端誤差剛好等於 target"""
    err0 = np.linalg.norm(traj[-1] - gt[-1])
    scale = 0.0 if err0 < 1e-9 else target / err0
    return gt + (traj - gt) * scale


def build_data():
    gt = ground_truth
    vo = normalize_error(build_vo(gt), gt, TARGET_VO_ERR)
    corr = normalize_error(build_corrected(gt), gt, TARGET_CORR_ERR)
    return {
        "room": ROOM,
        "markers": markers,
        "waypoints": waypoints,
        "ground_truth": gt.tolist(),
        "vo_trajectory": vo.tolist(),
        "corrected_trajectory": corr.tolist(),
    }


def write_outputs(data):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    js_block = (
        "<script>// __DATA_BEGIN__\n"
        "window.__VO_DATA__ = " + js + ";\n"
        "// __DATA_END__\n"
        "</script>"
    )
    with open(JS_PATH, "w", encoding="utf-8") as f:
        f.write("// 由 gen_fake_data.py 產生,勿手改\n")
        f.write("window.__VO_DATA__ = " + js + ";\n")
        f.write("if (typeof module !== 'undefined') module.exports = window.__VO_DATA__;\n")

    with open(HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    pattern = re.compile(
        r"<script>// __DATA_BEGIN__\n.*?// __DATA_END__\n</script>",
        re.S,
    )
    if not pattern.search(html):
        raise RuntimeError("HTML 中找不到 __DATA_BEGIN__ / __DATA_END__ 資料塊")
    html, n = pattern.subn(lambda _m: js_block, html)
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    return n


def main():
    data = build_data()
    n = write_outputs(data)
    n_f = len(data["ground_truth"])
    vo_err = float(np.linalg.norm(
        np.array(data["vo_trajectory"][-1]) - np.array(data["ground_truth"][-1])))
    corr_err = float(np.linalg.norm(
        np.array(data["corrected_trajectory"][-1]) - np.array(data["ground_truth"][-1])))
    print(f"已產生 {n_f} 幀假資料 -> fake_traj.json (+ data_embed.js)")
    print(f"已內嵌進 room_3d_demo.html (替換資料塊 x{n})")
    print(f"純VO軌跡末端誤差: {vo_err:.3f} m (目標 {TARGET_VO_ERR})")
    print(f"校正後軌跡末端誤差: {corr_err:.3f} m (目標 {TARGET_CORR_ERR})")


if __name__ == "__main__":
    main()