#!/bin/bash
L=/tmp/tumdl.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

echo "==TUMVI_ROOM1_PAGE_GET==" >> "$L"
timeout 25 wget -q -O /tmp/tumvi_room1.html "http://vision.in.tum.de/data/datasets/visual-inertial-dataset/room1" 2>&1 >> "$L" 2>&1
timeout 25 python3 -c "
import re
h=open('/tmp/tumvi_room1.html').read() if __import__('os').path.getsize('/tmp/tumvi_room1.html')>0 else ''
# bag類直接下載檔在 TUM-VI 是 vision.in.tum.de/tumvi/ 目錄, 抓頁面內所有 .bag / .zip 直鏈
urls=sorted(set(re.findall(r\"(?:href|src)=\"['\\\"]([^'\\\"]*?(?:room1[^'\\\"]*\.bag|\.bag|\.zip)[^'\\\"]*?)['\\\"]\",h)))
for u in urls[:14]: print('URL',u)
print('HREF_BAG_COUNT',len(urls))
" >> "$L" 2>&1

echo "==TUMVI_CALIB_DIR_LISTING==" >> "$L"
timeout 25 wget -q -O /tmp/tumvi_calib.html "http://vision.in.tum.de/tumvi/calibrated/512_16/" 2>&1 >> "$L" 2>&1
timeout 25 python3 -c "
import re
h=open('/tmp/tumvi_calib.html').read() if __import__('os').path.getsize('/tmp/tumvi_calib.html')>0 else ''
bag=re.findall(r\"href=\"([^\"]*?\.bag)\",h)
for b in sorted(set(bag))[:14]: print('BAG',b)
print('BAG_COUNT',len(set(bag)))
" >> "$L" 2>&1

echo "==TUMVI_HEAD_512_16_LATESTDIR==" >> "$L"
timeout 20 wget -q -O /tmp/tumvi_calib.html "http://vision.in.tum.de/tumvi/calibrated/" 2>&1
timeout 20 python3 -c "
import re
h=open('/tmp/tumvi_calib.html').read() if __import__('os').path.getsize('/tmp/tumvi_calib.html')>0 else ''
for m in re.findall(r\"href=\"([^\"]*?)\"\s*title=\\\"[^\"]*\\\"\s?>\s*([^<]*)\",h)[:10]: print(m)
" >> "$L" 2>&1

echo "==BAG_ACTUAL_BYTES_ATTEMPT(only if worked)==" >> "$L"
# Bags are ~2.2G+; we only do a real download if a direct .bag/.zip link was found above.
# This probe just reports what LINK topology looks like — download decision owned by caller.
echo "==END_TUMDL=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
