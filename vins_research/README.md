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

- 光照槽位: high n=18 median 0.234 / medium 0.449 / low 0.455 ⚠️ 三档实为同一 world，"光照"仅为标签（见下"光照轴实际未生效"）
- 轨迹: circle median 0.489 / figure8 0.182
- 明显离群 (ATE>2.0m, 5 组) 为 VINS 初始化的**单目随机尺度失败**（V/G 路径比 0.2–0.3），非光照/速度/轨迹系统性；同 cell 的健康重复 <0.8 m。中位数是稳健指标。详见 OUTLIER_ANALYSIS.md。

> **可复现性凭据**: 54 组的**实际运行脚本**是容器 `/tmp/trial_one.sh`
> （md5 `685adff44c2f7b90c74d2a2e2039d429`，备份 `scripts/trial_one.sh.as_run`，两者逐字节相同）。
> ⚠️ repo 版 `scripts/ops/trial_one.sh` 与它**并非逐字节相同**（`Compare-Object` 显示 22 行差异）：
> repo 版把 `/tmp`/`/root` 硬编码换成 `$REPO` 相对路径，并新增 bag 索引修复（`rosbag reindex`）
> 与 `evaluate_all.sh` 的 exit 3/4 处理。故 repo 版是**可移植复现版**，权威产物出自 `/tmp` 版。
> **2026-10-12 更新**：容器重建后 `/tmp/trial_one.sh` 已不存在；挂载的 `scripts/ops/trial_one.sh`
> 现为当前权威副本（md5 `384325554b12da942bb52f6b03695484`），在 `685adff44c2f7b90c74d2a2e2039d429`
> 基础上新增 `LIGHT`→`VINS_WORLD` 映射（真正切换光照世界）。原始主结果 54 组**仍出自
> `685adff…`**（备份 `scripts/trial_one.sh.as_run`，逐字节相同）。
> `data/`（bags/results/plots）为容器挂载产物，**不入库**。

> **重跑 / 归属规则 (2026-10-09)**: `trial_one.sh` 第 8 参数 `RUN_TAG` 把输出导向
> `<cell>_<tag>`（bag 与 `trial_<...>/` 均带 tag），同 cell 重跑**不再覆盖**先前产物；
> 每组结果落 `manifest.json`（md5: `sim_config.yaml` / `sim_launch.sh` / `light_*.world` / PX4 `<world>.world`）。
> 已知例外：`high / 1.5 / circle / r1` 的**首播原始 bag 已被一次重跑覆盖**，该重跑现标记为
> `..._r1_rep2`（ATE 0.495）；原始值 0.383 仅存于主表 `summary_54.csv`。

> **数据卫生 / stale 判定规则**: 主表 `summary_54.csv` 每行附 `trial_id` 与 `config_label`；
> 任何汇总行只要 `light ∉ {high,medium,low}` 或 `trajectory ∉ {circle,figure8}`
> （如 `sim`/`day0`/`night0`/`fig8`），一律隔离到 `data/results/summary_stale.csv`，不参与 54 组统计。

> **全矩阵复现重跑 (2026-10-10, RUN_TAG=repo54)**: 用 repo 版可移植脚本对整个 54 组重跑一遍，
> 产物在 `data/results_rerun54/`（`summary_54.csv`、`scale_sweep_repo54.csv`、
> `paired_master_repo54.csv`）。首轮 52/54 直接通过；2 组基础设施失败（Docker Desktop 两次
> 重启导致 guest 时钟跳变，详见 obs #0100）经**仅重跑**后补回 → **54/54 ok**，这 2 行标
> `config_label` 含 `rerun=infra`。
> 两版对比（`compare_master_rerun.py`）: 主表中位 ATE 0.365 m vs repo54 0.363 m；配对差
> 中位 **+0.009 m**（无系统性偏移，正负尾部对称）；scale 在带内 36/54 (67%) vs 37/54 (69%)。
> 逐 cell 差异为**单目初始化 / scale-collapse 的运行间随机性**，非脚本版本引入的系统效应。
> ⚠️ repo54 是"可移植版脚本"的产物，**不等于**主表 `/tmp` 版逐字节同源，比较时按上述口径解读。

> **suspect cell 重跑（2026-10-11，RUN_TAG=infra）**：对 `low/0.5/circle/r2`（原 repo54 行标
> `suspect_rtf`）单独重跑，得到干净的 `wall=184s / rtf=0.516 / imu_hz=50`——这正是重跑目的。
> 但其 `ATE_RMS=4.719 m` 与原始值**不可比**（master 0.375 m、repo54 原行 1.224 m），因 54 组
> 所用 `vins_demo.world` 在容器重建后遗失、现用**重建版**（md5 与原版 `1bcb504c…` 不同，场景特征
> 不同）。故该重跑仅作基础设施 datapoint，**不能**当作原 cell 的复现值。产物单行见
> `data/results_rerun54/infra_rerun.csv`（详见下方"容器重建"说明）。

> **#11 主表 × repo54 配对分析 + 失败率口径（2026-10-11）**：失败率有两个口径——
> (a) `ATE_RMS > 1 m`：**14/108（13%）**（主表 9 / repo54 5）；
> (b) scale gate `[0.96, 1.03]` 未通过：**34/107（32%）**（主表 17/53、repo54 17/54）。
> ⚠️ gate `[0.96,1.03]` 为**事后硬编码**（`report_stats.py:24`、`scale_gate.py:13` 等），非预注册；
> 同 cell 重复实测可散在 0.9–1.05。宽松口径 `[0.9,1.1]`：主表 43/53、repo54 47/54（合计 90/107）。
> `gate × ATE` 交叉表（合计）：带内＆ATE≤1 = **73**、带内＆ATE>1 = **0**、带外＆ATE≤1 = 20、
> 带外＆ATE>1 = 14、缺 scale = 1 —— 即 `ATE>1` 的离群**全部**落在 scale 带外（scale-collapse），
> 带内无一是失败。
> 逐光照 `ATE>1`（主表+repo54 合计）：**high 1/36、medium 4/36、low 9/36** —— 两批间方向一致，
> **但该模式不可归因于光照**（三档实为同一 world，见上/下"光照轴实际未生效"）。
> 18-cell（每 cell 取 3 rep 中位）逐 cell `ΔATE = repo54 − master`：median **+0.059 m**、
> 11 正 / 7 负（近似对称）；`|Δ|≤0.14 m` **10/18**、`0.14–0.16` 2/18、`>0.16` 6/18 → 差异为
> 单目初始化 / scale-collapse 的运行间随机性，非脚本版本引入的系统效应。

> **⚠️ 光照轴实际未生效（2026-10-11 核查，重要）**：54 组的 `light∈{high,medium,low}` **只是标签**，
> 三档跑的是**同一个世界文件**。证据链：
> - `batch_run_54.py:39` 实际调用 `scripts/ops/trial_one.sh`；该脚本把 `LIGHT`（$1）**仅用于命名**
>   trial 目录 / `TRIAL_ID` / manifest 标签，**从不映射到 world 文件**（`:20`）。
> - `trial_one.sh:16` `VINS_WORLD=${VINS_WORLD:-vins_demo}`、`docker/sim_launch.sh:7` 同款默认；
>   `sim_launch.sh:18` 把 `$VINS_WORLD` 传给 `sitl_run.sh` 作为世界名 → 全程 `vins_demo.world`。
> - 唯一真正加载 `worlds/light_${LIGHT}.world` 的是 `scripts/run_experiment.sh:25,59`（`roslaunch ... world:=`），
>   但它是**旁路脚本，不在 54 组矩阵的调用链上**。
> - manifest 自身即反证：`trial_one.sh:201` 记 `"vins_world": "vins_demo"`（实际使用），
>   而 `worlds/light_${LIGHT}.world` 的 md5（`:206`）只是被记录的**未被使用的**标签文件。
> **影响**：逐光照 `ATE>1`（1/36、4/36、9/36）与逐光照中位（0.234/0.449/0.455）
> **不能归因于光照**；三档差异只反映运行间随机性 / 基础设施时序（3 个 `suspect_rtf` 中 2 个属 low）。
> **报告正文不得据光照轴作结论**；光照条件的实际场景差异**待确认**。复现光照条件需改 `trial_one.sh`
> （按 `LIGHT` 设 `VINS_WORLD=light_${LIGHT}` 并同步 `light_*.world`）或走 `run_experiment.sh` 后重跑全矩阵。

> **主表 per-trial 产物污染（2026-10-11 核查）**：权威表 `data/results/summary_54.csv` 逐字节未变
> （md5 `a9a3ce6520bd7a40286008e7f65655a8`）。但该目录下**逐 trial 证据**在 10-09 之后被覆盖：
> `trial_high_1.5ms_circle_r1/` **缺失**，其 TUM（`high_1.5ms_circle_r1_{gt.tum,vins.txt}`，另有
> `sim_1.5ms_circle_r1_*`）被并入 `trial_high_0.5ms_circle_r1/trajectories/`；主表 `scale_sweep.csv`
> 将 `high_1.5ms_circle_r1` 记为 `MISSING`。**故汇总数值以 summary_54.csv 为准，该 cell 的
> per-trial 轨迹文件不可用于重建。**

> **时钟稳健性修复 (2026-10-10)**: `trial_one.sh` 的 `wall_s` 改用 bash `$SECONDS`（单调，
> 不受 guest 墙钟跳变影响），`batch_run_54.py` 的超时看门狗改用 `time.monotonic()`；
> 此前用 `date +%s` / `time.time()` 会在 Docker 重启后产生 `end<start` 的病态 `wall_s`/`rtf`
> （obs #0100）。`docker/docker-compose.yml` 增加 `init: true` 以回收僵尸进程（下次重建容器生效）。

> **容器重建 + 卫生 (2026-10-11)**：容器按 compose 重建后 PID1=`docker-init`（tini），僵尸
> 自行回收；50 Hz 基线与磁盘对照组经 `set_imu_hz.py` 自愈验证（build+ROMFS 两处
> `px4-rc.mavlink` 均回到 `f869fece…`）。`sim_config.yaml` 的 `output_path` 改到
> `/tmp/vins_out/`，VINS 自产物（`vins_result*.csv`）不再污染 `/data/results/` 主表目录。
> **仿真资产现已烤入镜像（2026-10-11）**：gazebo-classic 插件、渲染后的 jinja 模型、自定义
> 世界/模型（`vins_demo.world`、`vins_props`）、GeographicLib 大地水准面、以及 3 个
> `sitl_run.sh` 补丁，全部由 `docker/setup_sim_assets.sh`（幂等）在镜像构建时装好；容器重建后
> 也可在容器内直接重跑该脚本自愈（3 个补丁脚本均已改为幂等）。⚠️ 注意：`vins_demo.world`
> 原版已丢失，烤入的是**重建版**（见上文 suspect cell 重跑说明），故其 ATE 与原始 54 组
> 不可直接比较。

> **#12 同会话对照与离群判别 (2026-10-11)**：对 2 个被标记 cell（`high/0.5/circle`、
> `medium/3.0/figure8`）×3 rep×2 臂在同一次会话交错重跑（`scripts/ops/rerun_pair.py` +
> `run5_ctl_pair.sh`，RUN_TAG=imu161r/ctl50，12/12 ok）。
> **结论 1（原 r2 bump 未重现）**：`high/0.5/circle` 原 imu161 r2=1.30 m 在同会话 imu161r
> r2 仅 0.28 m（scale 带内）→ 单次单目初始化随机性，非 125 Hz 系统性。
> **结论 2（本批数据看不出 125Hz 与 50Hz 的差别，不写"不劣于"）**：12 次中 8 次 scale 在
> gate[0.96,1.03] 外，gate 外 ATE 不可信、不可取中位数；gate 内样本（125Hz 0.28/0.24 vs
> 50Hz 0.97）无同 cell 可配对。且同 cell 同臂 ATE 可在 0.28–4.95 间跳变，变异大于任何臂间
> 差异；崩溃率在 n=12 下也比不出（两侧皆 0/12）。
> **⚠️ 主机状态依赖（比 IMU 结论更重要）**：本会话两臂绝对 ATE 都显著偏高（ctl50 中位 0.90
> vs #9 的 50 Hz 健康值 0.36–0.50，scale 8/12 离带），说明**结果高度依赖主机状态**，不只是
> 单目随机性。因此：54 组 matrix 的绝对数值只在特定主机状态下可重现；跨 session（Docker
> Desktop 重启、主机睡眠恢复后）的比较**只能信同 session 配对的差分**，单方绝对 ATE 不具可比性。
> **推论（2026-10-11）**：任何单方绝对 ATE（含本次 infra 重跑的 4.719 m）都只在产生它的那个
> 主机/环境状态下有意义，不得直接与其他 session 的数对标。
> 判别脚本 `compare_suspect_cells.py`、图 `data/plots/suspect_cells_5arms.png`。

> **IMU 高采样率子实验 (#12, 2026-10-10, RUN_TAG=imu161)**: 把 mavros `/mavros/imu/data_raw`
> 协商为 200 Hz（`sim_launch.sh` 每次启动按 `IMU_HZ` 环境变量调用 `docker/set_imu_hz.py` 改写
> PX4 `px4-rc.mavlink` 的 `mavlink stream -s HIGHRES_IMU`，默认 50 Hz，幂等、启动后自动复位）。
> 实测 HIGHRES_IMU 协商失败（PX4 无定义该 rate）时由 IMU+baro 填充，**按 bag sim 时间测得
> 实际约 125 Hz（min 125.0 / median 125.0 / max 126.5）**，故标签用 `imu161` 并如实标注 ~125 Hz，
> 不用 200 Hz。6 cell × 3 rep 交错（rep-major, `scripts/ops/run12_subset.py`）单线程跑，
> 结果在 `data/results_imu161/`。
> **结果 18/18 ok、零 crash/hang**；中位 ATE **0.326 m**（master 50Hz 0.302 / repo54 50Hz 0.346，
> 均指同一 18 cell 子集），中位 RTF 0.518（略慢于 50Hz 的 ~0.55，符合消息量增大的代价），
> scale 带内 17/18（离带：`medium_3.0ms_figure8_r3` 0.9472）。逐 cell 与两 50Hz 臂的 |ΔATE|
> 大都落在 ±0.14 m 运行间噪声内，**未观察到系统性精度劣化**（注：这个 18-cell 子集的绝对
> 数值是跨 session 的，按下方"主机状态依赖"警告只作参考）；3 个臂都有少量离群运行
> （master 3 个 ATE≥2.8 m、repo54 2 个、imu161 1 个：`high_0.5ms_circle_r2` 1.299 m，
> 以及 1 个 scale 离带），判定为单目初始化的运行间随机性。流程加固（flock 单实例锁、
> kill_chain 后残留进程 precheck、watchdog 仅告警不重启）保证全链 18/18 无重试、无重复链。

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
| 光照 | 高 (ambient 0.8) / 中 (0.4) / 低 (0.1) ⚠️ 未实际生效：54 组均跑 vins_demo.world |
| 速度 | 0.5 / 1.5 / 3.0 m/s |
| 轨迹 | 圆形 (A) / 8字形 (B) |
| 重复 | 3 次/组 |
| 总数 | 3×3×2×3 = 54 次 |