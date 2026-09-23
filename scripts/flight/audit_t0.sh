#!/bin/bash
L=/tmp/audit_t0.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

# 1) 乾淨殺掉舊 sim 鏈(保留 roscore pid)
pkill -x gzserver 2>/dev/null; pkill -x px4 2>/dev/null
pkill -f sitl_run.sh 2>/dev/null; pkill -f sim_launch.sh 2>/dev/null; pkill -f sim60 2>/dev/null
sleep 4
echo "==SIM_KILLED=$(date -u +%H:%M:%S)==" >> "$L"

# 2) 用「wire60 證實 full-rate 的那條鏈」重啟真正 fresh window
cd /root/PX4-Autopilot/build/px4_sitl_default
DISPLAY=:99 nohup bash /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh \
  /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 none iris_fpv_cam empty \
  /root/PX4-Autopilot /root/PX4-Autopilot/build/px4_sitl_default \
  > /tmp/audit_sim.log 2>&1 &
echo "==SIM_RELAUNCHED=$(date -u +%H:%M:%S)==" >> "$L"

# 3) 等 px4 真的起來(streaming register),煞車到 full-rate 窗口內
for i in $(seq 1 40); do
  pgrep -x px4 >/dev/null && break
  sleep 1
done
echo "==PX4_UP=$(date -u +%H:%M:%S)==" >> "$L"

# 4) 第二-0 起 audi-only companion(綁 0.0.0.0:14540,無 send —— raw 全速、已證)
#    用一根「診斷專用」裸 listener,這顆是飛行線唯一 socket
nohup python3 /tmp/companion4.py > /tmp/audit_cmp.log 2>&1 &
echo "==COMPANION_LAUNCHED=$(date -u +%H:%M:%S)==" >> "$L"

# 5) 趁窗口:清點可錄 topic(不 inline,python 檔一次探)
cat > /tmp/audit_topics.py <<'PYEOF'
import subprocess, time
out = []
def rb(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        return r.stdout
    except Exception as e:
        return "ERR %s" % e
time.sleep(6)
lst = rb(["rostopic","list"])
ims = [l for l in lst.splitlines() if "Image" in l or "image" in l or "cam" in l.lower()]
imus= [l for l in lst.splitlines() if "imu" in l.lower() or "IMU" in l]
print("==TOTAL_TOPICS=%d==" % len(lst.splitlines()))
print("==IMAGE_TOPICS==")
for l in ims: print("  ", l)
print("==IMU_TOPICS==")
for l in imus: print("  ", l)
print("==EXAMPLE_IMU_TYPE==")
print(rb(["rosmsg","show","sensor_msgs/Imu"])[:200])
print("==DONE_AUDIT=%s==" % time.strftime("%H:%M:%S"))
PYEOF
timeout 40 python3 /tmp/audit_topics.py >> "$L" 2>&1

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
