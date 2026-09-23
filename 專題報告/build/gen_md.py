# -*- coding: utf-8 -*-
"""匯出改寫整理稿 .md — deliverable #4（來源: report_content.py 單一內容來源）"""
import sys
sys.path.insert(0, r"D:\Things\專題報告\build")
import report_content as rc

OUT = r"D:\Things\專題報告\deliverables\專題報告_改寫整理稿.md"

L = []

def emit_toc():
    L.append("| 章節 | 標題 |")
    L.append("|---|---|")
    for s in rc.SECTIONS:
        L.append(f"| {s['no']} | {s['title']} |")
    L.append("| 附錄 A | 關鍵技術名詞對照 |")
    L.append("")

def emit_blocks(blocks, indent=""):
    for b in blocks:
        t = b[0]
        if t == "p":
            L.append(b[1].replace("**", "**"))
        elif t == "bullet":
            L.append(f"- {b[1]}")
        elif t == "num":
            L.append(f"1. {b[1]}")
        elif t == "note":
            L.append(f"> {b[1]}")
        elif t == "pre":
            L.append("```")
            L.append(b[1])
            L.append("```")
        elif t == "table":
            hdr = b[1]
            rows = b[2]
            if len(b) > 3 and b[3]:
                L.append(f"**{b[3]}**")
                L.append("")
            L.append("| " + " | ".join(hdr) + " |")
            L.append("|" + "|".join(["---"] * len(hdr)) + "|")
            for r in rows:
                L.append("| " + " | ".join(x.replace("|", "／") for x in r) + " |")
        elif t == "img":
            path, caption = b[1], b[2] if len(b) > 2 else ""
            md_path = path.replace("figs/", "../build/figs/")
            L.append(f"![{caption}]({md_path})")
            if caption:
                L.append(f"**{caption}**")
        L.append("")

with open(OUT, "w", encoding="utf-8") as f:
    L = []
    L.append(f"# {rc.TITLE}")
    L.append("")
    L.append(f"## {rc.SUBTITLE}")
    L.append("")
    L.append(f"> {rc.OUTPUT_MD_VERSION}")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 摘要")
    L.append("")
    emit_blocks(rc.ABSTRACT)
    L.append(f"**關鍵詞：** {rc.KEYWORDS}")
    L.append("")
    L.append("---")
    L.append("")
    emit_toc()
    L.append("---")
    L.append("")
    for s in rc.SECTIONS:
        L.append(f"## {s['no']}、{s['title']}")
        L.append("")
        for sub in s["subs"]:
            L.append(f"### {sub['no']}　{sub['title']}")
            L.append("")
            emit_blocks(sub["blocks"])
    L.append(f"## {rc.APPENDIX_TITLE}")
    L.append("")
    hdr = rc.APPENDIX_TABLE["headers"]
    L.append("| " + " | ".join(hdr) + " |")
    L.append("|" + "|".join(["---"] * len(hdr)) + "|")
    for r in rc.APPENDIX_TABLE["rows"]:
        L.append("| " + " | ".join(r) + " |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 參考文獻")
    L.append("")
    for i, r in enumerate(rc.REFERENCES, 1):
        L.append(f"[{i}] {r}")
    L.append("")
    L.append("---")
    L.append("")
    L.append("*本文稿為改寫整理版，所有實驗數據皆忠實沿用原始 專題.txt 內容，未更動任何數值。*")
    f.write("\n".join(L))

print("MD_WRITTEN", OUT)