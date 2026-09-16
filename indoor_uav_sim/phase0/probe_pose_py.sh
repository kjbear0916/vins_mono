#!/usr/bin/env bash
# probe_pose_py.sh — verify gz sim pose/info topic then subscribe via python transport13
set -u
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
LOG=/tmp/px4gz_pose.log

mkdir -p "$HOME/bin"
install -m 755 /mnt/d/Things/indoor_uav_sim/phase0/bin/gz "$HOME/bin/gz"
export PATH="$HOME/bin:$PATH"

pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null; sleep 2
cd "$HOME/PX4-Autopilot" || exit 1
make px4_sitl gz_x500 > "$LOG" 2>&1 &
MAKE_PID=$!

up=0
for i in $(seq 1 40); do
  sleep 3
  if pgrep -f 'bin/px4' >/dev/null 2>&1 && pgrep -f 'gz sim' >/dev/null 2>&1; then up=1; break; fi
done
echo "boot up=$up after $((i*3))s"
[ "$up" != 1 ] && { echo FAIL; tail -c 2000 "$LOG"; exit 1; }
sleep 20

echo "=== gz sim serves pose/info? ==="
timeout 6 gz topic -e -t /world/default/pose/info -n 1 2>&1 | head -12

echo "=== python transport13 subscribe to pose/info (15s) ==="
cat > /tmp/pose_sub.py <<'PYEOF'
import sys, time
from gz import transport13
from gz.msgs10 import pose_pb2

got = []
def cb(msg, info):
    for p in msg.pose:
        if p.name:  # collect any named entity
            got.append((p.name, p.position.x, p.position.y, p.position.z))

node = transport13.Node()
node.subscribe(pose_pb2.Pose_V, "/world/default/pose/info", cb)
t0 = time.time()
while time.time() - t0 < 15:
    time.sleep(0.2)
    if got:
        break
node.unsubscribe(pose_pb2.Pose_V, "/world/default/pose/info")

for n in list(dict.fromkeys([g[0] for g in got]))[:25]:
    m = [g for g in got if g[0] == n][-1]
    print(f"entity={m[0]} pos=({m[1]:.3f},{m[2]:.3f},{m[3]:.3f})")
print(f"total_pose_msgs={len(got)}")
PYEOF
python3 /tmp/pose_sub.py 2>&1 | head -40

kill $MAKE_PID 2>/dev/null
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo cleaned