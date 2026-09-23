# -*- coding: utf-8 -*-
"""PDF 驗證：頁數、A4 尺寸、關鍵數據與文字（obs 0039）"""
from pypdf import PdfReader

PDF = r"D:\Things\專題報告\deliverables\專題報告_室內無人機自主導航.pdf"
import sys
if len(sys.argv) > 1:
    PDF = sys.argv[1]
LOG = r"D:\Things\專題報告\build\check_pdf.log"

r = PdfReader(PDF)
n = len(r.pages)
mb = r.pages[0].mediabox
w, h = float(mb.width), float(mb.height)
texts = []
for pg in r.pages:
    texts.append(pg.extract_text() or "")
allt = "\n".join(texts)

print("PAGES", n, "MB", w, h)

lines = []
lines.append(f"PAGES={n}")
lines.append(f"MEDIABOX={w:.1f}x{h:.1f}")
A4W, A4H = 595.3, 841.9
lines.append(f"A4_CHECK={'PASS' if (abs(w-A4W)<3 and abs(h-A4H)<3) or (abs(h-A4W)<3 and abs(w-A4H)<3) else 'FAIL'}")

spot = [
    "室內無人機自主導航之感知定位子系統",
    "Bundle Adjustment",
    "17/17", "2.4", "154", "108/201", "431", "k3", "1640",
    "seq_real_14", "76.9", "Sim3", "52 毫米", "ArUco", "P1",
]
for s in spot:
    ok = s in allt
    lines.append(f"{'PASS' if ok else 'FAIL'}  text[{s}]")
    print("TEXT_CHECK", s, ok)

# TOC page numbers should have been inserted by Word update
toc_present = ("目錄" in allt)
lines.append(f"TOC_PRESENT={'PASS' if toc_present else 'FAIL'}")

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("VERIFY_PDF_DONE")