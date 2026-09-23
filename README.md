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

### 实验流程

**1. 运行单个实验**
```bash
bash scripts/run_experiment.sh high 1.5 circle 1
```

**2. 运行全部 54 组实验**
```bash
bash scripts/run_all_experiments.sh
```

**3. 评估所有结果**
```bash
bash scripts/evaluation/evaluate_all.sh
```

**4. 生成可视化图表**
```bash
python3 scripts/evaluation/make_plots.py
```

**5. 统计分析**
```bash
python3 scripts/analysis/statistical_analysis.py
```

**6. 一键全流程**
```bash
bash scripts/full_pipeline.sh
```

### 目录结构
```
vins_research/
├── docker/              # Docker 环境配置
├── config/              # VINS-Mono 配置文件
├── launch/               # ROS launch 文件
├── worlds/              # Gazebo 光照世界文件
├── scripts/
│   ├── flight/          # 航点飞行控制
│   ├── evaluation/      # 轨迹提取、EVO 评估、可视化
│   ├── analysis/        # 统计分析、日志扫描
│   └── run_*.sh         # 一键运行脚本
└── data/
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