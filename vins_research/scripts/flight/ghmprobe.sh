#!/bin/bash
L=/tmp/ghm.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

echo "==VINS_CONFIG_DIR_FULL==" >> "$L"
ls -R /root/catkin_ws/src/VINS-Mono/config | grep -vE '^$' | head -30 >> "$L" 2>&1

echo "==GH_API_SEARCH_EUROC_MIRROR==" >> "$L"
timeout 20 curl -sH "Accept: application/vnd.github+json" \
  "https://api.github.com/search/repositories?q=euroc+dataset+in:name,description&sort=stars&per_page=6" \
  | grep -oE '"full_name": ?"[^"]+"|"clone_url": ?"[^"]+"|"pushed_at": ?"[^"]+"' | head -18 >> "$L" 2>&1

echo "==GH_RELEASES_VINS_EUROC_ASSET==" >> "$L"
timeout 20 curl -sH "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/HKUST-Aerial-Robotics/VINS-Mono/releases/latest" \
  | grep -oE '"name": ?"[^"]+"|"browser_download_url": ?"[^"]+"|"message": ?"[^"]+"' | head -12 >> "$L" 2>&1

echo "==GH_CODE_SEARCH_MH01_BAG==" >> "$L"
timeout 20 curl -sH "Accept: application/vnd.github+json" \
  -H "User-Agent: vins-research" \
  "https://api.github.com/search/code?q=MH_01_easy.bag+in:path" \
  | grep -oE '"total_count": ?[0-9]+|"html_url": ?"[^"]+"|"message": ?"[^"]+"' | head -12 >> "$L" 2>&1

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
