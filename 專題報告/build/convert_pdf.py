# -*- coding: utf-8 -*-
"""透過 Word COM 更新功能變數並匯出 PDF（deliverable #2）"""
import sys
import win32com.client
import pythoncom

DOCX = r"D:\Things\專題報告\deliverables\專題報告_室內無人機自主導航.docx"
PDF = r"D:\Things\專題報告\deliverables\專題報告_室內無人機自主導航.pdf"
if len(sys.argv) > 2:
    DOCX = sys.argv[1]
    PDF = sys.argv[2]

pythoncom.CoInitialize()
word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
try:
    doc = word.Documents.Open(DOCX, ReadOnly=False)
    for f in doc.Fields:
        f.Update()
    for i in range(1, doc.TablesOfContents.Count + 1):
        doc.TablesOfContents.Item(i).Update()
    doc.Repaginate()
    doc.Save()
    doc.ExportAsFixedFormat(OutputFileName=PDF, ExportFormat=17)
    print("PDF_WRITTEN_OK")
    doc.Close(False)
finally:
    word.Quit()