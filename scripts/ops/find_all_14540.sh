#!/bin/bash
echo "=== all UDP sockets on port 38CC (14540) ==="
grep -i 38CC /proc/net/udp
echo "=== map each inode ===
"
for ino in $(grep -i 38CC /proc/net/udp | awk '{print $9}'); do
  echo "--- inode $ino ---"
  for p in /proc/[0-9]*; do
    pid=$(basename $p)
    for fd in $p/fd/*; do
      t=$(readlink "$fd" 2>/dev/null)
      if [ "$t" = "socket:[$ino]" ]; then
        echo "   PID=$pid COMM=$(cat /proc/$pid/comm 2>/dev/null) EXE=$(readlink /proc/$pid/exe 2>/dev/null)"
      fi
    done
  done
done
echo "=== mavros_node process ==="
ps -eo pid,ppid,args | grep mavros_nod[e] | cut -c1-60