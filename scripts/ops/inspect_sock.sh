#!/bin/bash
INO=$(grep -i 38CC /proc/net/udp | head -1 | awk '{print $9}')
echo "inode=$INO"
for p in /proc/[0-9]*; do
  for fd in $p/fd/*; do
    t=$(readlink "$fd" 2>/dev/null)
    if [ "$t" = "socket:[$INO]" ]; then
      echo "SOCK_OWNER=$p"
    fi
  done
done
sleep 3
echo "=== rx after 3s ==="
grep -i 38CC /proc/net/udp | head -1
echo "=== mavros alive ==="
ps -eo pid,args | grep mavros_nod[e] | cut -c1-45