# -*- coding: utf-8 -*-
"""簡報視覺 QA：PowerPoint 匯出 PDF → pymupdf 渲染縮圖"""
import pythoncom
import win32com.client

PPTX = r"D:\Things\專題報告\deliverables\專題簡報_感知定位子系統.pptx"
PDF = r"D:\Things\專題報告\build\pptx_preview.pdf"

pythoncom.CoInitialize()
ppt = win32com.client.DispatchEx("PowerPoint.Application")
try:
    pres = ppt.Presentations.Open(PPTX, ReadOnly=True, WithWindow=False)
    pres.SaveAs(PDF, 32)  # 32 = ppSaveAsPDF
    pres.Close()
    print("PPTX_PDF_OK")
finally:
    ppt.Quit()