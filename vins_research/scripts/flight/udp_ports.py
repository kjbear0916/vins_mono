import re
from collections import Counter

ports = Counter()
for line in open("/proc/net/udp"):
    parts = line.split()
    if len(parts) < 2 or "local_address" in parts[0]:
        continue
    local = parts[1].split(":")
    if len(local) == 2:
        try:
            ports[int(local[1], 16)] += 1
        except ValueError:
            pass

interesting = [14540, 14550, 14557, 14580, 18570, 14280, 13030, 14030, 13280]
print("interesting UDP binds:")
for p in interesting:
    print("  %5d : %s" % (p, ports.get(p, 0) and "BOUND" or "free"))
print("all local ports:", sorted(ports))