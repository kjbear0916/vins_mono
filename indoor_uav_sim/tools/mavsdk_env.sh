#!/bin/bash
set +u
echo "== mavsdk_server binary search =="
find / -name 'mavsdk_server*' -type f 2>/dev/null | head
find / -path '*mavsdk*' -name '*.whl' 2>/dev/null | head
python3 -c "import mavsdk, os; print(os.path.dirname(mavsdk.__file__))"
echo "== net check =="
timeout 6 curl -sI https://github.com 2>&1 | head -3
timeout 6 curl -sI https://pypi.org 2>&1 | head -3