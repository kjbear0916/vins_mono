# VINS-Mono 无人机仿真专题 — 研究说明

## 研究题目
探讨光照变化与飞行速度对 VINS-Mono 定位精度的影响，并分析失效原因。

## 研究假设
1. **H1**: 光照强度越低 → 特征点数量越少 → ATE(绝对轨迹误差)越大
2. **H2**: 飞行速度越快 → 运动模糊与特征跟踪失败概率越高 → RPE(相对位姿误差)越大

## 系统架构
```
┌─────────────────────────────────────────────────────────────┐
│                    Gazebo (SITL 仿真环境)                    │
│                                                             │
│   World (光照档位: 高/中/低)                                 │
│      ├─ Iris 无人机模型                                       │
│      │    ├─ 单目相机插件  → /camera/image_raw                │
│      │    └─ IМУ 插件       → /mavros/imu/data_raw             │
│      └─ Ground Truth 位姿 → /gazebo/model_states              │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│  PX4-Autopilot (SITL)  ↔  MAVROS  ↔  ROS Noetic              │
│         │                                                     │
│         └─ 发送航点指令 (offboard 模式, 固定轨迹+速度)          │
└───────────────┬─────────────────────────────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────┐
│  VINS-Mono                                                    │
│                                                               │
│   feature_tracker ← /camera/image_raw                         │
│   estimator      ← features + /mavros/imu/data_raw            │
│   output: /vins_estimator/path, /vins_estimator/odometry       │
└───────────────┬─────────────────────────────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────┐
│  rosbag 录制  →  轨迹提取 (TUM格式)  →  EVO 评估                │
│                                                 │            │
│   VINS path  ──────────────┐                   ▼              │
│                           ├─→ evo_ape (ATE) → CSV            │
│   Gazebo GT  ──────────────┘  evo_rpe (RPE) → 统计检验          │
│                                                │              │
│                                                 ▼              │
│                                       matplotlib 图表 + 报告    │
└─────────────────────────────────────────────────────────────┘
```

## 实验设计

| 维度 | 设置 |
|---|---|
| 光照 (世界文件) | `light_high.world` (ambient 0.8) / `light_medium.world` (0.4) / `light_low.world` (0.1) |
| 速度 (控制脚本) | 0.5 m/s / 1.5 m/s / 3.0 m/s |
| 轨迹 (固定轨迹) | 圆形 (半径5m) / 8字形 |
| 重复次数 | 每组 3 次 |
| 总数 | 3 × 3 × 2 × 3 = **54 次** |

## 评估指标
- **ATE** (Absolute Trajectory Error, 绝对轨迹误差) — 用 `evo_ape`
- **RPE** (Relative Pose Error, 相对位姿误差) — 用 `evo_rpe`
- 输出: RMSE / median / mean / std / max

## 失效判据
- VINS 跟踪丢失 (tracking failure)
- VINS 初始化失败 (init failure)
- ATE 突增 (>2m 或 超过组内中位数 5 倍)
- 特征点数量骤降 (<50)

## 关键脚本
| 脚本 | 功能 |
|---|---|
| `scripts/run_experiment.sh` | 一键运行单组实验 |
| `scripts/run_all_experiments.sh` | 批量运行全部 54 组 |
| `scripts/evaluation/extract_trajectories.py` | bag → TUM 轨迹 |
| `scripts/evaluation/evaluate_all.sh` | EVO 批量评估 → CSV |
| `scripts/evaluation/make_plots.py` | 可视化图表 |
| `scripts/analysis/statistical_analysis.py` | ANOVA + t 检验 |
| `scripts/analysis/failure_analysis.py` | 失效案例分析 |
| `scripts/analysis/scan_vins_logs.py` | VINS 日志特征统计 |
| `scripts/full_pipeline.sh` | 全流程一键执行 |

## 潜在风险与规避
1. **PX4/Gazebo 启动慢** — 预留等待时间, 复用容器避免反复构建
2. **Ceres 版本不兼容** — Dockerfile 固定 1.14.0
3. **VINS 无输出** — 检查 topic 映射 (`/camera/image_raw`, `/mavros/imu/data_raw`)
4. **低光下特征不足** — 可能需要调低 `min_dist` 或调高相机增益/曝光
5. **实机差距** — 仿真中相机无噪点/畸变, 结论需在局限性中说明