# -*- coding: utf-8 -*-
"""span 層級重疊檢查（避免 pymupdf block 合併的假陽性）"""
import pymupdf

doc = pymupdf.open(r'D:\Things\專題報告\build\pptx_preview.pdf')
res = []
for i, page in enumerate(doc):
    d = page.get_text('dict')
    spans = []
    for blk in d['blocks']:
        if blk['type'] != 0:
            continue
        for ln in blk['lines']:
            for sp in ln['spans']:
                if sp['text'].strip():
                    spans.append(sp)
    for a in range(len(spans)):
        for c in range(a + 1, len(spans)):
            A, B = spans[a], spans[c]
            x0a, y0a, x1a, y1a = A['bbox']
            x0b, y0b, x1b, y1b = B['bbox']
            ix = max(0, min(x1a, x1b) - max(x0a, x0b))
            iy = max(0, min(y1a, y1b) - max(y0a, y0b))
            if ix > 1 and iy > 1:
                res.append(f"p{i+1} A[{A['text'][:18]}] B[{B['text'][:18]}] ix={ix:.0f} iy={iy:.0f}")

out = r'D:\Things\專題報告\build\qa\span_issues.txt'
with open(out, 'w', encoding='utf-8') as f:
    f.write("\n".join(res) if res else 'NO_SPAN_OVERLAP')
print('SPAN_OVERLAPS', len(res))
for x in res:
    print(x)