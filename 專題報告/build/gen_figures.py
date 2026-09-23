# -*- coding: utf-8 -*-
"""產製報告示意圖與數據圖（fig1–fig6 → D:\\Things\\專題報告\\build\\figs\\）"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle
import matplotlib.patheffects as pe

FIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
os.makedirs(FIG_DIR, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Noto Sans TC", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 11

PRIMARY = "#1F4E79"
ACCENT = "#4472C4"
RED = "#C00000"
GREEN = "#2E7D32"
GRAY = "#595959"
LIGHT = "#DCE6F2"


def save(fig, name, dpi=200):
    fig.savefig(os.path.join(FIG_DIR, name), dpi=dpi, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    print("FIG", name)


# ========================================================= fig1 整體處理流程
def fig1():
    fig, ax = plt.subplots(figsize=(8.2, 8.8))
    ax.set_xlim(0, 10); ax.set_ylim(0, 11.2); ax.axis("off")

    steps = [
        ("ESP32S3-CAM\n影像串流（WiFi / MJPEG）", PRIMARY),
        ("特徵偵測與光流追蹤\n（Shi-Tomasi ＋ Lucas-Kanade）", ACCENT),
        ("增量式 PnP 定位 ＋ 局部地圖三角化\n（關鍵幀、RANSAC）", ACCENT),
        ("Bundle Adjustment\n全局優化", ACCENT),
        ("ArUco Marker 絕對座標校正\n（可選，Sim3 對齊）", "#7F6000"),
        ("軌跡輸出\n與定量驗證", GREEN),
    ]
    n = len(steps)
    y_start, y_end = 10.6, 0.9
    ys = np.linspace(y_start, y_end, n)
    bw, bh, cx = 6.8, 1.25, 5.0
    for i, ((txt, col), y) in enumerate(zip(steps, ys)):
        box = FancyBboxPatch((cx - bw / 2, y - bh / 2), bw, bh,
                             boxstyle="round,pad=0.06",
                             fc=LIGHT, ec=col, lw=2)
        ax.add_patch(box)
        ax.text(cx, y, txt, ha="center", va="center", fontsize=11.5,
                color="black", linespacing=1.45)
    for ya, yb in zip(ys[:-1], ys[1:]):
        ax.add_patch(FancyArrowPatch((cx, ya - bh / 2 - 0.02), (cx, yb + bh / 2 + 0.02),
                                     arrowstyle="-|>", mutation_scale=22,
                                     lw=2.2, color=GRAY))
    ax.text(cx, 0.25, "步驟 1 → 6：輸入影像至產出可用軌跡", ha="center",
            va="center", fontsize=10, color=GRAY, style="italic")
    save(fig, "fig1_pipeline.png")


# ========================================================= fig2 系統架構
def fig2():
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    ax.set_xlim(0, 16); ax.set_ylim(0, 6.2); ax.axis("off")

    # 機載端
    ax.add_patch(FancyBboxPatch((0.6, 1.1), 4.6, 4.0, boxstyle="round,pad=0.08",
                                fc="#FBE5D6", ec="#C55A11", lw=2))
    ax.text(2.9, 4.7, "機載端（無人機）", ha="center", fontsize=12, fontweight="bold",
            color="#C55A11")
    ax.add_patch(FancyBboxPatch((1.0, 2.9), 3.8, 1.3, boxstyle="round,pad=0.05",
                                fc="white", ec="#C55A11", lw=1.5))
    ax.text(2.9, 3.55, "ESP32S3-CAM\n機載影像擷取", ha="center", va="center", linespacing=1.4)
    ax.add_patch(FancyBboxPatch((1.0, 1.4), 3.8, 1.2, boxstyle="round,pad=0.05",
                                fc="white", ec="#C55A11", lw=1.5))
    ax.text(2.9, 2.0, "WiFi 無線傳輸\n（STA 模式、固定 IP）", ha="center", va="center",
            linespacing=1.4)

    # 主機端
    ax.add_patch(FancyBboxPatch((7.0, 0.9), 8.4, 4.4, boxstyle="round,pad=0.08",
                                fc=LIGHT, ec=PRIMARY, lw=2))
    ax.text(11.2, 4.9, "接收運算端（主機）", ha="center", fontsize=12, fontweight="bold",
            color=PRIMARY)
    mods = [
        ("MJPEG 串流解析\n（幀序號／時間戳）", 3.9),
        ("視覺里程計前端\n（PnP ＋ 局部地圖）", 2.9),
        ("Bundle Adjustment", 1.9),
        ("標定／驗證／視覺化", 0.9),
    ]
    for txt, y in mods:
        ax.add_patch(FancyBboxPatch((7.4, y), 7.6, 0.85, boxstyle="round,pad=0.05",
                                    fc="white", ec=ACCENT, lw=1.5))
        ax.text(11.2, y + 0.425, txt, ha="center", va="center", fontsize=10,
                linespacing=1.25)

    ax.add_patch(FancyArrowPatch((6.3, 2.4), (6.95, 2.9), arrowstyle="-|>",
                                 mutation_scale=20, lw=2.5, color=GRAY))
    ax.text(6.62, 2.0, "MJPEG\n串流", ha="center", fontsize=9, color=GRAY)
    save(fig, "fig2_arch.png")


# ========================================================= fig3 ArUco 定位示意
def fig3():
    try:
        import cv2
        dic = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        mk = cv2.aruco.generateImageMarker(dic, 23, 90)
        mk2 = cv2.aruco.generateImageMarker(dic, 7, 90)
        mk3 = cv2.aruco.generateImageMarker(dic, 41, 90)
        use_cv = True
    except Exception:
        use_cv = False
        mk = (np.random.rand(90, 90, 3) * 255).astype(np.uint8)

    fig, ax = plt.subplots(figsize=(9.4, 6.0))
    ax.set_xlim(0, 12); ax.set_ylim(0, 7.6); ax.axis("off")

    # 天花板/牆面
    ax.add_patch(Rectangle((0.6, 4.6), 10.8, 2.6, fc="#EAF1FB", ec=ACCENT, lw=1.5))
    ax.text(6.0, 6.95, "測試空間牆面／天花板（Marker 已知絕對座標）", ha="center",
            fontsize=12, fontweight="bold", color=PRIMARY)

    def place(img, x, y, s=1.15, label=None):
        im = ax.imshow(img, extent=(x, x + s, y, y + s), zorder=5)
        if label:
            ax.text(x + s / 2, y - 0.32, label, ha="center", fontsize=10, color=GRAY)
        return (x + s / 2, y + s / 2)

    if use_cv:
        c1 = place(mk, 1.6, 5.1, 1.0)
        c2 = place(mk2, 5.5, 5.0, 1.0)
        c3 = place(mk3, 9.1, 5.1, 1.0)
    else:
        c1 = c2 = c3 = (6.0, 5.6)

    # 相機
    ax.add_patch(FancyBboxPatch((3.4, 0.6), 5.2, 2.2, boxstyle="round,pad=0.08",
                                fc="#E2EFDA", ec=GREEN, lw=2))
    ax.text(6.0, 1.7, "相機（VO 估計之相對軌跡）", ha="center", va="center",
            fontsize=11.5, fontweight="bold")
    ax.text(6.0, 0.9, "" , ha="center")

    for c in (c1, c2, c3):
        ax.add_patch(FancyArrowPatch((6.0, 2.85), c, arrowstyle="-|>", mutation_scale=16,
                                     lw=1.6, color=ACCENT, linestyle="dashed",
                                     connectionstyle="arc3,rad=0.08"))
    # Sim3 標籤
    ax.add_patch(FancyBboxPatch((3.0, 3.0), 6.0, 0.9, boxstyle="round,pad=0.06",
                                fc="#FFF2CC", ec="#BF8F00", lw=1.5))
    ax.text(6.0, 3.45, "solvePnPGeneric → 絕對座標 ＋ Sim3 對齊整條軌跡",
            ha="center", va="center", fontsize=11)
    save(fig, "fig3_aruco.png")


# ========================================================= fig4 BA 誤差條圖
def fig4():
    fig, ax = plt.subplots(figsize=(7.4, 4.9))
    labels = ["BA 前", "BA 後"]
    vals = [3577, 26]
    colors = [RED, GREEN]
    bars = ax.bar(labels, vals, color=colors, width=0.5, edgecolor="black", lw=1)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 60, f"{v:,} px", ha="center",
                fontsize=13, fontweight="bold")
    ax.set_ylabel("重投影誤差（像素，軌跡累計）")
    ax.set_title("Bundle Adjustment 對累積漂移之改善（合成資料）", fontsize=13,
                 fontweight="bold", color=PRIMARY, pad=14)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.text(0.5, -0.16, "約 100 倍改善（3577 → 26 px）", transform=ax.transAxes,
            ha="center", fontsize=11, color=GRAY, style="italic")
    save(fig, "fig4_ba_improve.png")


# ========================================================= fig5 標定敏感度
def fig5():
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    cats = ["原始\n(cy 異常)", "修正 cy", "修正 cy 與 cx"]
    ate = [154.19, 154.16, 161.12]
    scale = [870.6, 744.6, 851.4]
    x = np.arange(3)
    w = 0.34
    b1 = ax.bar(x - w / 2, ate, w, color=ACCENT, edgecolor="black", lw=0.8, label="Post-BA ATE（mm）")
    ax.set_ylabel("ATE（mm）")
    ax.set_ylim(0, 200)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    for xi, v in zip(x - w / 2, ate):
        ax.text(xi, v + 4, f"{v:.2f}", ha="center", fontsize=10.5)
    ax2 = ax.twinx()
    b2 = ax2.bar(x + w / 2, scale, w, color="#ED7D31", edgecolor="black", lw=0.8,
                 label="座標縮放尺度（mm/unit）")
    ax2.set_ylabel("座標縮放尺度（mm/unit）")
    ax2.set_ylim(0, 1000)
    ax2.spines["top"].set_visible(False)
    for xi, v in zip(x + w / 2, scale):
        ax2.text(xi, v + 12, f"{v:.1f}", ha="center", fontsize=10.5)
    ax.set_xticks(x); ax.set_xticklabels(cats)
    ax.set_title("相機內參敏感度分析（真機序列）", fontsize=13, fontweight="bold",
                 color=PRIMARY, pad=14)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", fontsize=10, frameon=False, ncol=2)
    ax.text(0.5, -0.14, "ATE 最大變異約 4.5%（強健）；尺度變異約 14%（敏感）",
            transform=ax.transAxes, ha="center", fontsize=10.5, color=GRAY, style="italic")
    save(fig, "fig5_calib_sens.png")


# ========================================================= fig6 精度對照
def fig6():
    fig, ax = plt.subplots(figsize=(8.8, 5.1))
    cats = ["本系統\n(合成)", "本系統\n(真機)", "ORB-SLAM3", "VINS-Mono",
            "ORB-SLAM2", "OpenVINS"]
    vals = [2.6, 154, 30, 90, 80, 50]   # mm（EuRoC 由 m 換算，V1_01）
    colors = [GREEN, RED, ACCENT, ACCENT, ACCENT, ACCENT]
    bars = ax.bar(cats, vals, color=colors, width=0.6, edgecolor="black", lw=0.8)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 4, f"{v}", ha="center",
                fontsize=10, fontweight="bold")
    ax.set_yscale("log")
    ax.set_ylim(1, 500)
    ax.set_ylabel("位置誤差（mm，對數刻度）")
    ax.set_title("精度量級對照（本系統 vs 公開基準 EuRoC V1_01）", fontsize=13,
                 fontweight="bold", color=PRIMARY, pad=14)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.text(0.5, -0.14,
            "＊ EuRoC 系統為視覺慣性（含 IMU），本系統為單目無 IMU、無回環；僅量級參考並非直接可比",
            transform=ax.transAxes, ha="center", fontsize=9.5, color=GRAY, style="italic")
    save(fig, "fig6_precision.png")


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4(); fig5(); fig6()
    print("ALL_FIGS_OK")