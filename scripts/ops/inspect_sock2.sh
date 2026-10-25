#!/bin/bash
for try in 1 2 3; do
  INO=$(grep -i 38CC /proc/net/udp | head -1 | awk '{print $9}')
  [ -n "$INO" ] && break
  sleep 2
done
echo "inode=$INO"
for p in /proc/[0-9]*; do
  for fd in $p/fd/*; do
    t=$(readlink "$fd" 2>/dev/null)
    if [ "$t" = "socket:[$INO]" ]; then
      echo "SOCK_OWNER=$(basename $p) $(cat /proc/$(basename $p)/comm 2>/dev/null)"
    fi
  done
done
echo "=== rx t0 ==="
grep -i 38CC /proc/net/udp | head -1
sleep 5
echo "=== rx t+5s ==="
grep -i 38CC /proc/net/udp | head -1
echo "=== mavros log tail ==="
tail -3 /tmp/mavros10.log | cut -c1-120