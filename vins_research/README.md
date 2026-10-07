# VINS-Mono 无人机仿真专题
## 光照变化与飞行速度对 VINS-Mono 定位精度的影响

### 环境要求
- Docker Desktop (推荐) 或 WSL2 Ubuntu 20.04
- 至少 8GB RAM, 20GB 磁盘空间
- 支持 OpenGL 的 GPU (可选, 用于 Gazebo 渲染)

### 快速开始

**方式 1: Docker (推荐)**

```bash
# 构建环境 (~30 分钟)
bash scripts/docker_setup.sh

# 启动环境
docker compose -f docker/docker-compose.yml up
```

**方式 2: WSL2 手动安装**

```bash
# 在 WSL2 Ubuntu 20.04 中
wget https://packages.ros.org/ros.key -O - | sudo apt-key add -
sudo sh -c 'echo "deb http://packages.ros.org/ros/ubuntu focal main" > /etc/apt/sources.list.d/ros-noetic.list'
sudo apt update
sudo apt install -y ros-noetic-desktop-full python3-rosdep python3-catkin-tools
sudo rosdep init && rosdep update
# 然后继续按照 plan 安装 PX4、MAVROS、Ceres、VINS-Mono
```

### 实验流程（固化逻辑 2026-10-07）

**1. 运行单个 trial**
```bash
# trial_one.sh <light> <traj> <speed> <radius> <alt> <flight_dur> <repeat>
bash scripts/ops/trial_one.sh high circle 1.5 5.0 3.0 45 1
```

**2. 运行 54 组矩阵 / 指定 cell**
```bash
python3 scripts/ops/batch_run_54.py                 # 全组
python3 scripts/ops/batch_run_54.py --light high --speed 1.5 --traj circle --repeat 1   # 单 cell
# TRIAL_SCRIPT 环境变量可指向其它 trial 脚本，默认 scripts/ops/trial_one.sh（SCRIPT_DIR 定位）
```

**3. 按 bag 名过滤评估**
```bash
# evaluate_all.sh <bag_dir> <out_dir> <bag_pattern>
bash scripts/evaluation/evaluate_all.sh /data/rosbags /data/results sim_1.5ms_circle_r1
# 零匹配 → exit 3；评价失败 (gt_empty/vins_empty/evo_ate_failed) → exit 4
```

**4. 验收阈值门 + 报告**
```bash
python3 scripts/analysis/scale_gate.py data/results/summary_54.csv
python3 scripts/analysis/acceptance_report.py data/results/summary_54.csv
```

**5. 真值 z 剖面检查**
```bash
python3 scripts/analysis/realbag_z.py <bag_path>    # 从 /gazebo/model_states 提取 iris 高度
```

### 54 组验收结果

| 指标 | 修复前 (camera-up, 平灰地面) | 修复后全矩阵 |
|---|---|---|
| 初始化成功 | — | 54/54 (ALL init ok) |
| ATE_RMS 中位数 | — | **0.365 m** |
| RPE_RMS 中位数 | — | 0.040 m |
| Scale | 0.012–0.036 | ~1.07 |

- 光照槽位: high n=18 median 0.234 / medium 0.449 / low 0.455
- 轨迹: circle median 0.489 / figure8 0.182
- 明显离群 (ATE>2.0m, 5 组) 为 VINS 初始化的**单目随机尺度失败**（V/G 路径比 0.2–0.3），非光照/速度/轨迹系统性；同 cell 的健康重复 <0.8 m。中位数是稳健指标。详见 OUTLIER_ANALYSIS.md。

> **可复现性凭据**: 54 组实际运行逻辑固化为 `scripts/ops/trial_one.sh`；
> 容器 `/tmp/trial_one.sh` 权威副本 md5 `685adff44c2f7b90c74d2a2e2039d429`（备份 `.as_run`）。
> `data/`（bags/results/plots）为容器挂载产物，**不入库**。

### 目录结构
```
vins_research/
├── docker/              # Docker 环境配置 (sim_launch.sh 权威版, VINS_WORLD 透传)
├── config/              # VINS-Mono 配置文件
├── launch/               # ROS launch 文件
├── worlds/              # Gazebo 光照世界文件
├── scripts/
│   ├── flight/          # init_motion.py, 航点飞行控制
│   ├── ops/             # trial_one.sh, batch_run_54.py, validate_bags.sh
│   ├── evaluation/      # 轨迹提取、EVO 评估、evaluate_all.sh
│   ├── analysis/        # realbag_z.py, scale_gate.py, acceptance_report.py
│   └── run_*.sh         # 一键运行脚本
└── data/                # 实验数据 (gitignored)
    ├── rosbags/         # 实验录制数据
    ├── results/         # 评估结果
    └── plots/           # 生成图表
```

### 实验参数

| 变量 | 取值 |
|---|---|
| 光照 | 高 (ambient 0.8) / 中 (0.4) / 低 (0.1) |
| 速度 | 0.5 / 1.5 / 3.0 m/s |
| 轨迹 | 圆形 (A) / 8字形 (B) |
| 重复 | 3 次/组 |
| 总数 | 3×3×2×3 = 54 次 |