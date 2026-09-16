#!/usr/bin/env bash
# probe_pose_py2.sh — real python transport13 subscription test
set -u
export GZ_SIM_RESOURCE_PATH="$HOME/PX4-Autopilot/Tools/simulation/gz/models"
export PX4_SIM_MODEL=gz_x500
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
LOG=/tmp/px4gz_pose2.log

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

echo "=== python transport13 subscribe to pose/info (20s) ==="
cat > /tmp/pose_sub.py <<'PYEOF'
import time
from gz import transport13
from gz.msgs10 import pose_v_pb2

class C:
    def __init__(self):
        self.count = 0
        self.entities = {}

def cb(msg):
    c.names = set(p.name for p in msg.pose if p.name)
    for p in msg.pose:
        if p.name == 'x500_0':
            c.drone = (p.position.x, p.position.y, p.position.z)

c = C()
node = transport13.Node()
node.subscribe(pose_v_pb2.Pose_V, "/world/default/pose/info", cb)
t0 = time.time()
while time.time() - t0 < 20:
    time.sleep(0.2)
    if getattr(c, 'drone', None):
        break
node.unsubscribe("/world/default/pose/info")

if getattr(c, 'name', None) is None and getattr(c, 'names', None):
    print("entities seen:", sorted(c.names))
if getattr(c, 'drone', None):
    print("DRONE pose = ({:.3f}, {:.3f}, {:.3f})".format(*c.drone))
else:
    print("NO x500_0 pose seen in 20s")
PYEOF
python3 /tmp/pose_sub.py 2>&1 | head -30

kill $MAKE_PID 2>/dev/null
pkill -f 'gz sim' 2>/dev/null; pkill -f 'bin/px4' 2>/dev/null
echo cleaned