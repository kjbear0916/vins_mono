import json
import urllib.request

url = "https://pypi.org/pypi/egm96/0.3.0/json"
with urllib.request.urlopen(url, timeout=60) as r:
    meta = json.load(r)
for u in meta["urls"]:
    print(u["filename"], u["url"], u["size"])