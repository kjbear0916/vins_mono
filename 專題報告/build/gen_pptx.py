# -*- coding: utf-8 -*-
"""產生上台簡報 .pptx（deliverable #3）16:9"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION

OUT = r"D:\Things\專題報告\deliverables\專題簡報_感知定位子系統.pptx"

SW, SH = 13.333, 7.5
PRIMARY = RGBColor(0x1F, 0x4E, 0x79)
ACCENT = RGBColor(0x44, 0x72, 0xC4)
DARK = RGBColor(0x26, 0x26, 0x26)
GRAY = RGBColor(0x59, 0x59, 0x59)
LIGHT = RGBColor(0xF2, 0xF6, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
EA = "Microsoft JhengHei"


def set_ea(run):
    rPr = run._r.get_or_add_rPr()
    from pptx.oxml.ns import qn
    ea = rPr.makeelement(qn('a:ea'), {'typeface': EA})
    rPr.append(ea)


def add_textbox(slide, x, y, w, h, text, size=16, bold=False, color=DARK,
                align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = EA
    set_ea(run)
    run.font.color.rgb = color
    return tb


def add_para(tf, text, size=16, bold=False, color=DARK, level=0, align=PP_ALIGN.LEFT,
             space_after=6, bullet=True):
    p = tf.add_paragraph()
    p.level = level
    p.alignment = align
    p.space_after = Pt(space_after)
    prefix = ""
    if bullet and level == 0:
        prefix = "▪ "
    elif bullet and level == 1:
        prefix = "– "
    run = p.add_run()
    run.text = prefix + text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = EA
    set_ea(run)
    run.font.color.rgb = color
    return p


def title_bar(slide, title, page_no=None):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.12), Inches(0.62))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    add_textbox(slide, 0.45, 0.05, 11.5, 0.6, title, size=26, bold=True, color=PRIMARY)
    if page_no:
        add_textbox(slide, 12.2, 7.05, 0.9, 0.35, str(page_no), size=11, color=GRAY,
                    align=PP_ALIGN.RIGHT)


def bullets_slide(slide, items, x=0.7, y=1.15, w=12.0, h=5.7, size=17):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for it in items:
        if isinstance(it, tuple):
            text, lvl = it
        else:
            text, lvl = it, 0
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        p.level = lvl
        p.space_after = Pt(8)
        prefix = "▪ " if lvl == 0 else "– "
        run = p.add_run()
        bold = lvl == 0 and text.startswith("**")
        t = text.replace("**", "")
        run.text = prefix + t
        run.font.size = Pt(size if lvl == 0 else size - 2)
        run.font.bold = bold
        run.font.name = EA
        set_ea(run)
        run.font.color.rgb = DARK if lvl == 0 else GRAY
    return tb


def make_table(slide, rows, x, y, w, h, col_w, font_size=11.5, row_h_in=0.42):
    nr, nc = len(rows), len(rows[0])
    gf = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(h))
    tbl = gf.table
    tbl.first_row = True
    tbl.horz_banding = True
    for c, cw in enumerate(col_w):
        tbl.columns[c].width = Inches(cw)
    for r in range(nr):
        tbl.rows[r].height = Inches(row_h_in)
        for c in range(nc):
            cell = tbl.cell(r, c)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.04)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if (r == 0 or c == 0) else PP_ALIGN.LEFT
            run = p.add_run()
            run.text = rows[r][c]
            run.font.size = Pt(font_size)
            run.font.name = EA
            set_ea(run)
            if r == 0:
                run.font.bold = True
                run.font.color.rgb = WHITE
                cell.fill.solid(); cell.fill.fore_color.rgb = PRIMARY
            else:
                run.font.color.rgb = DARK
                if r % 2 == 0:
                    cell.fill.solid(); cell.fill.fore_color.rgb = LIGHT
                else:
                    cell.fill.solid(); cell.fill.fore_color.rgb = WHITE
    return tbl


def add_chart_ba(slide):
    chart_data = CategoryChartData()
    chart_data.categories = ["BA 前", "BA 後"]
    chart_data.add_series("重投影誤差（像素）", (3577, 26))
    x, y, w, h = Inches(2.3), Inches(3.1), Inches(8.7), Inches(3.6)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, w, h, chart_data)
    chart = gf.chart
    chart.has_legend = False
    chart.has_title = True
    chart.chart_title.text_frame.text = "合成資料：Bundle Adjustment 誤差改善（像素）"
    for run in chart.chart_title.text_frame.paragraphs[0].runs:
        run.font.size = Pt(14); run.font.name = EA; set_ea(run)
    chart.font.name = EA
    chart.font.size = Pt(12)
    plot = chart.plots[0]
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.show_value = True
    dl.number_format = "0"
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(13)
    dl.font.bold = True
    series = plot.series[0]
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = ACCENT
    cat_ax = chart.category_axis
    cat_ax.tick_labels.font.name = EA
    val_ax = chart.value_axis
    val_ax.has_major_gridlines = True
    val_ax.tick_labels.font.size = Pt(10)
    val_ax.axis_title.text_frame.text = "重投影誤差（像素）"
    for run in val_ax.axis_title.text_frame.paragraphs[0].runs:
        run.font.size = Pt(12); run.font.name = EA; set_ea(run)
    return gf


def add_big_stat(slide, num, label, x, y, w, h):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r1 = p.add_run(); r1.text = num
    r1.font.size = Pt(40); r1.font.bold = True; r1.font.name = EA; set_ea(r1)
    r1.font.color.rgb = PRIMARY
    r1.font.name = EA
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = label
    r2.font.size = Pt(12.5); r2.font.name = EA; set_ea(r2)
    r2.font.color.rgb = GRAY


prs = Presentation()
prs.slide_width = Inches(SW)
prs.slide_height = Inches(SH)
blank = prs.slide_layouts[6]


def new_slide():
    return prs.slides.add_slide(blank)


# ================================================================ 1 封面
s = new_slide()
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid(); bg.fill.fore_color.rgb = PRIMARY
bg.line.fill.background()
strip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(2.55), Inches(0.7), Inches(0.09))
strip.fill.solid(); strip.fill.fore_color.rgb = ACCENT
strip.line.fill.background()
add_textbox(s, 0.9, 0.9, 11.5, 0.5, "專題報告", size=18, color=RGBColor(0xBF, 0xD3, 0xEE))
add_textbox(s, 0.9, 2.55, 11.5, 1.1, "室內無人機自主導航之\n感知定位子系統", size=40, bold=True,
            color=WHITE)
add_textbox(s, 0.9, 3.95, 11.5, 0.6, "純視覺里程計與 Bundle Adjustment 軌跡估計與驗證", size=20,
            color=RGBColor(0xC5, 0xD8, 0xEF))
add_textbox(s, 0.9, 5.5, 11.5, 1.4,
            "系所／組員：【請填寫】    指導老師：【請填寫】\n中華民國 115 年（2026 年）",
            size=14, color=RGBColor(0xDB, 0xE6, 0xF4))

# ================================================================ 2 大綱
s = new_slide()
title_bar(s, "報告大綱", 2)
items = [
    "研究背景與轉折 · 問題本質",
    "研究範圍界定與系統架構",
    "核心技術方法：增量式 PnP 前端 · Bundle Adjustment · 七道驗證閘門",
    "相關開源模型對照 與 公開基準（EuRoC）技術定位",
    "實驗結果：合成資料驗證 · 真機資料驗證 · 誠實落差分析",
    "延伸模組：ArUco Marker 絕對定位",
    "視覺化展示 · 研究貢獻 · 限制與未來工作",
]
bullets_slide(s, items, y=1.5, size=20)
s.notes_slide.notes_text_frame.text = "本報告約 12–15 分鐘，重點放在方法與驗證架構。"

# ================================================================ 3 背景與轉折
s = new_slide()
title_bar(s, "研究背景與轉折", 3)
bullets_slide(s, [
    "原始題目：室內無人機自主導航系統（移動＋避障）",
    "開發過程中飛行載具損壞 → 不換題目，聚焦核心子問題：",
    ("**室內、無 GPS 下，無人機如何準確估計自身位置？**", 1),
    "為什麼這個轉折合理：",
    ("定位（Localization）與控制（Control）為相對獨立子系統", 1),
    ("定位不準，路徑規劃與飛控再好也無法可靠運作", 1),
    "驗證載體改為手持／手推模擬飛行軌跡：",
    ("不影響定位演算法有效性，同時大幅降低風險與複雜度", 1),
], size=17)

# ================================================================ 4 問題本質
s = new_slide()
title_bar(s, "問題本質：室內為什麼無法用 GPS？", 4)
bullets_slide(s, [
    "GPS 依賴衛星訊號，室內因牆體遮蔽而大幅衰減甚至完全消失",
    "所有室內自主移動載具（無人機、掃地機器人、倉儲物流機器人等）都需要替代定位",
    "主流解法之一：**視覺里程計（Visual Odometry, VO）**",
    ("由相機連續影像估算自身相對起點的移動軌跡", 1),
    ("不需額外感測器，成本低、適用性廣", 1),
    "本研究聚焦：**純視覺**（僅單一相機）＋ 誤差修正（Bundle Adjustment）",
])

# ================================================================ 5 範圍界定
s = new_slide()
title_bar(s, "研究範圍界定", 5)
rows = [
    ["項目", "本研究範圍", "原因／後續規劃"],
    ["感測器", "僅單一相機（純視覺）", "IMU 融合列為未來工作"],
    ["定位性質", "相對定位為主軸＋Marker 輔助絕對定位", "完整 SLAM 列為未來工作"],
    ["誤差修正", "Bundle Adjustment 全局優化", "Loop Closure 列為未來工作"],
    ["驗證載體", "手持／手推模擬飛行軌跡", "不涉及實際飛行與馬達"],
    ["座標系", "房間自訂相對座標＋Marker 絕對座標", "不涉及 GPS／經緯度換算"],
]
make_table(s, rows, 0.7, 1.35, 11.9, 4.4, [1.7, 6.2, 4.0], font_size=12)

# ================================================================ 6 系統架構
s = new_slide()
title_bar(s, "系統架構：硬體與資料傳輸", 6)
tb = s.shapes.add_textbox(Inches(0.7), Inches(1.2), Inches(12.0), Inches(5.6))
tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]
r = p.add_run(); r.text = "硬體組成"
r.font.size = Pt(17); r.font.bold = True; r.font.name = EA; set_ea(r); r.font.color.rgb = PRIMARY
for it in [
    ("▪ ESP32S3-CAM：機載影像擷取端，WiFi / MJPEG 串流", 0),
    ("▪ 接收運算端：執行 VO、Bundle Adjustment 與分析", 0),
]:
    add_para(tf, it[0].replace("▪ ", ""), size=16, level=it[1], space_after=6, bullet=True)
add_para(tf, "傳輸架構與開發陷阱", size=17, bold=True, color=PRIMARY, bullet=False, space_after=4)
for it in [
    ("▪ STA 模式＋固定 IP；自行實作 MJPEG multipart 解析，保留幀序號／時間戳供同步", 0),
    ("▪ 初期 AP 模式因 Windows NCSI 判定「無網際網路」而頻繁自動斷線 → 改 STA 根本解決", 0),
]:
    add_para(tf, it[0].replace("▪ ", ""), size=16, level=0, space_after=6, bullet=True)
add_para(tf, "處理流程", size=17, bold=True, color=PRIMARY, bullet=False, space_after=4)
add_para(tf, "影像串流 → 特徵偵測／光流追蹤 → 增量式 PnP＋局部地圖三角化 → Bundle Adjustment"
             " →（可選）ArUco 絕對座標校正 → 軌跡輸出與定量驗證",
         size=16, space_after=4)

# ================================================================ 7 VO 前端
s = new_slide()
title_bar(s, "VO 前端：增量式 PnP ＋ 局部地圖", 7)
rows = [
    ["步驟", "內容", "設計重點"],
    ["1. 座標系初始化", "kf0 為世界原點；kf1 以 Essential Matrix 建立初始基線", "建立基準"],
    ["2. 特徵追蹤", "Shi-Tomasi 角點 ＋ Lucas-Kanade 光流", "跨關鍵幀追蹤"],
    ["3. 增量三角化", "跨幀 2D 觀測三角化出 3D 地圖點，持續累積", "建立局部地圖"],
    ["4. 強健定位", "新關鍵幀以 solvePnPRansac 對照地圖定位", "抗尺度漂移／誤差累積"],
]
make_table(s, rows, 0.7, 1.3, 11.9, 3.6, [1.6, 6.0, 4.3], font_size=12.5)
add_textbox(s, 0.7, 5.35, 12.0, 1.2,
            "目的：以「地圖點對照」取代純逐幀相對估計，從根本緩解尺度漂移與誤差累積。",
            size=15, color=GRAY, bold=True)

# ================================================================ 8 關鍵問題
s = new_slide()
title_bar(s, "開發過程：四大關鍵問題與修復", 8)
rows = [
    ["問題", "解決方式"],
    ["Bootstrap 死鎖（PnP↔三角化互依）", "補 kf0 slot-0 觀測；地圖點不足時退回 Essential Matrix"],
    ["追蹤 ID 錯位（存活點與 ID 未同步）", "實作 _surviving_ids 重建正確對應"],
    ["Reset 邏輯過於敏感（頻繁無謂重置）", "0 特徵才硬重置；偏低僅補充特徵點"],
    ["視差角過小致三角化品質差", "視差角 < 2° 之點捨棄，避免污染地圖"],
]
make_table(s, rows, 0.7, 1.35, 11.9, 3.4, [4.4, 7.5], font_size=12.5)
add_textbox(s, 0.7, 5.3, 12.0, 1.0,
            "這些是增量式 SLAM 前端在實務上最常見的難點；除錯記錄與驗證數據皆完整保留。",
            size=15, color=GRAY, bold=True)

# ================================================================ 9 BA
s = new_slide()
title_bar(s, "Bundle Adjustment：全局優化修正累積漂移", 9)
bullets_slide(s, [
    "聯合最佳化**所有關鍵幀位姿 ＋ 地圖點 3D 座標**，最小化全數觀測的重投影誤差",
    "合成資料改善：約 **3577 px → 26 px**（約 **100 倍**）",
    "證明 BA 對修正長時間運行累積漂移有顯著效果",
], y=1.25, size=17, h=1.7)
add_chart_ba(s)

# ================================================================ 10 開源模型對照
s = new_slide()
title_bar(s, "相關開源模型與技術定位", 10)
rows = [
    ["系統", "方法路線", "關鍵能力（★ 2026-09 GitHub 觀測）"],
    ["ORB-SLAM2／ORB-SLAM3", "特徵式（＋視覺慣性）", "回環偵測、重定位、多子地圖（★10.2k／9.1k）"],
    ["DSO／SVO", "直接／半直接法", "高精度、輕量即時（★2.5k／2.2k）"],
    ["VINS-Mono／Fusion", "視覺慣性（優化式）", "IMU 緊耦合、尺度可觀（★6.0k）"],
    ["OpenVINS／Kimera-VIO", "濾波式 VIO／語意", "研究平台、度量語意地圖（★3.1k／1.9k）"],
    ["g2o／GTSAM／Ceres", "後端最佳化", "位姿圖優化、因子圖、Bundle Adjustment"],
    ["DBoW2／hloc／evo", "回環・重定位・評估", "詞袋檢索、大規模定位、ATE／RPE 標準工具"],
]
make_table(s, rows, 0.7, 1.2, 11.9, 3.5, [3.5, 3.2, 5.2], font_size=11.5, row_h_in=0.46)
add_textbox(s, 0.7, 4.95, 12.0, 1.4,
            "本系統＝「特徵追蹤＋局部地圖＋PnP＋BA」之精簡純視覺架構，與 DSO／SVO 同路線。\n"
            "公開基準（EuRoC）：視覺慣性系統可達公分級（ORB-SLAM3 RMS 位置誤差 0.03 m）；本系統真機 ATE ≈ 154 mm。\n"
            "能力邊界：缺 IMU 融合、回環偵測與重定位 → 已逐項對應可採用之開源方案。",
            size=13.5, color=GRAY, bold=True)

# ================================================================ 11 七道閘門
s = new_slide()
title_bar(s, "自動化驗證方法論：七道驗證閘門（P1–P7）", 11)
bullets_slide(s, [
    "P1 軌跡連續性　-　P2 重投影一致性（含 BA 前後比較）",
    "P3 直線度　-　P4 單調性　-　P5 跳點偵測",
    "P6 結構量門檻（關鍵幀／特徵點數量）　-　P7 靜止段光流檢驗",
    "在**合成正、負對照組**上皆測試，確保閘門能真正區分「好／壞資料」",
    "避免落入「系統看起來能動」就宣稱有效的主觀驗證",
], size=18)

# ================================================================ 12 合成資料
s = new_slide()
title_bar(s, "實驗結果 ①：合成資料驗證", 12)
add_big_stat(s, "17 / 17", "七道閘門全數通過", 0.7, 1.6, 3.0, 1.3)
add_big_stat(s, "2.4–2.8 mm", "ATE（六組測試組合）", 4.3, 1.6, 3.8, 1.3)
add_big_stat(s, "20 / 20", "演算法回歸測試", 8.6, 1.6, 3.0, 1.3)
bullets_slide(s, [
    "自行開發**合成序列產生器**：模擬乾淨、可控的移動軌跡，提供精確地面真值",
    "完整通過 → 證明 VO 前端與 BA 演算法邏輯本身正確",
    "為後續真機驗證建立可信的技術基礎",
], y=3.3, size=16)

# ================================================================ 13 真機資料
s = new_slide()
title_bar(s, "實驗結果 ②：真機資料驗證（seq_real_14）", 13)
bullets_slide(s, [
    "5×4 棋盤格（25 mm 方格）提供地面真值：成功捕獲 **108/201 幀（53.7%）**",
    "局部地圖：**431 個三維地圖點、26 個關鍵幀**",
    "重投影誤差：Pre-BA 2.05 px → **Post-BA 1.24 px**（收斂 RMS 0.87）",
    "驗證閘門：P1、P2、P6、P7 通過；P3／P4／P5 因手持移動限制未通過（已歸因、記錄）",
    "**ATE ≈ 154 mm**（20/26 幀具地面真值對照，覆蓋率 76.9%）",
    ("結論：端到端定位管線在真實環境中可運作、可量化", 1),
], size=16.5)

# ================================================================ 14 落差與標定
s = new_slide()
title_bar(s, "誠實落差分析 與 相機標定反思", 14)
bullets_slide(s, [
    "真機 vs 合成 ATE 落差約 **60 倍**（154 vs 2.4–2.8 mm），成因：",
    ("地面真值量測精度、光照雜訊、標定殘差、76.9% 覆蓋率", 1),
    "標定陷阱①：imageSize 順序錯誤 → cy=30.6 異常（敏感度分析：",
    ("ATE 變異 ≤ **4.5%** → 對主點偏移強健；座標尺度變異 **14%** → 對內參敏感", 1),
    "標定陷阱②：焦距－畸變耦合退化（k3 = -1640）→ 要求姿態多樣性＋物理合理性檢查",
    "態度：數值、失敗與限制**如實揭露**，不選擇性報告",
], size=15.5)

# ================================================================ 15 ArUco
s = new_slide()
title_bar(s, "延伸模組：ArUco Marker 室內絕對定位", 15)
bullets_slide(s, [
    "目標：把「相對座標」升級為具物理意義的「絕對座標」",
    "三步驟：標記部署＋量測 → solvePnPGeneric 姿態估算 → **Sim3 對齊**整條軌跡",
    "合成驗證：自測 0.000 mm　·　端到端平均誤差 **52 mm**　·　閘門 **5/5**　·　回歸 **26/26**",
    "**尚待完成**：實體硬體驗證（標記列印、佈署量測、真機穩定度與精度）",
    "限制：不跨場地遷移、精度受限量測工具（±5–10 mm）、標記可視範圍外退化、無重定位",
], size=16)

# ================================================================ 16 視覺化
s = new_slide()
title_bar(s, "視覺化 與 航點導航模擬", 16)
bullets_slide(s, [
    "3D 房間模型呈現測試空間，標示各標記絕對位置",
    "並列顯示「純 VO 軌跡」（累積漂移）vs「標記校正後軌跡」（貼近真實路徑）",
    "支援靜態檢視與動畫回放",
    "**航點導航模擬**：即時計算方向／距離，到達判定後自動切換下一目標",
    ("演示「自主移動載具導航決策」之概念；完成實體驗證後可直接替換真實資料", 1),
], size=17)

# ================================================================ 17 貢獻與未來
s = new_slide()
title_bar(s, "研究貢獻 ・ 限制與未來工作", 17)
add_textbox(s, 0.7, 1.15, 6.0, 0.45, "研究貢獻", size=17, bold=True, color=PRIMARY)
bullets_slide(s, [
    "完整可重現的純視覺定位鏈（VO→BA→驗證）",
    "兩類標定陷阱之量化分析與方法論",
    "誠實實驗設計與限制揭露",
    "相對→絕對定位之技術路徑驗證",
    "與開源生態／公開基準之對照定位",
], x=0.7, y=1.6, w=5.9, size=13.5)
add_textbox(s, 7.0, 1.15, 6.0, 0.45, "限制與未來工作", size=17, bold=True, color=PRIMARY)
bullets_slide(s, [
    "IMU 融合：角速度積分加入 BA 殘差項（參照 VINS／OpenVINS）",
    "回環＋重定位：DBoW2＋g2o／GTSAM（參照 ORB-SLAM2／3）",
    "延伸模組實體驗證＋AprilTag 標記選型評估",
], x=7.0, y=1.6, w=5.9, size=13.5)

# ================================================================ 17 結論
s = new_slide()
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid(); bg.fill.fore_color.rgb = PRIMARY
bg.line.fill.background()
add_textbox(s, 1.2, 0.9, 10.9, 0.6, "結論", size=30, bold=True, color=WHITE)
add_textbox(s, 1.2, 1.8, 10.9, 4.6,
            "▪ 純視覺定位系統：合成＋真機雙重定量驗證（ATE 2.4–2.8 mm / ≈154 mm）\n"
            "▪ 嚴謹方法論：七道驗證閘門、敏感度分析、誠實落差揭露\n"
            "▪ 延伸：ArUco 絕對定位＋Sim3 座標校正＋視覺化導航原型\n"
            "▪ 對照：與 ORB-SLAM／VINS／OpenVINS 等開源模型及 EuRoC 基準明確定位能力邊界\n\n"
            "核心價值不在「能動的系統」，而在完整可驗證、誠實面對限制的研究態度。",
            size=17, color=WHITE)
add_textbox(s, 1.2, 5.6, 10.9, 0.9, "謝謝聆聽　敬請指教", size=24, bold=True,
            color=RGBColor(0xC5, 0xD8, 0xEF))

prs.core_properties.title = "室內無人機自主導航之感知定位子系統"
prs.core_properties.subject = "純視覺里程計與 Bundle Adjustment 軌跡估計與驗證"
prs.core_properties.author = "專題研究團隊"
prs.save(OUT)
print("PPTX_WRITTEN_OK")