# 离群样本分析（主表 54 组）

> 本文回应 README「54 组验收结果」一节的引用：**明显离群（ATE>2.0 m，5 组）不是光照/速度/轨迹的系统效应，
> 而是单目初始化的运行间随机失败**。判据、证据与处置规则如下。

## 1. 判据

| 标记 | 定义 | 来源 |
|---|---|---|
| ATE 离群 | `ate_rms > 2.0 m` | `data/results/summary_54.csv` |
| 尺度崩溃 | `sim3_scale ∉ [0.96, 1.03]` | `data/results/scale_sweep.csv` |
| 路径比异常 | `path_ratio < 0.5`（VINS 轨迹长度 / 真值轨迹长度） | 同上 |

`scale` 由 Umeyama Sim3 对齐得到，是判断「单目尺度是否成立」的唯一外部参照。
单目 VINS 的尺度在初始化后不可观测，一旦初始化的两帧视差不足或纯旋转，
整段轨迹会整体缩放，ATE 随之爆掉 —— 这是**尺度崩溃**，不是跟踪失败。

## 2. 五个 ATE>2.0 m 的样本

| trial_id | ATE (m) | RPE (m) | sim3_scale | path_ratio | 判定 |
|---|---|---|---|---|---|
| `low_1.5ms_figure8_r1` | 4.18 | 0.2432 | 1.109 | 0.268 | 路径塌缩 |
| `medium_0.5ms_circle_r1` | 3.60 | 0.1579 | 3.614 | 0.314 | 尺度崩溃 |
| `low_0.5ms_figure8_r2` | 3.55 | 0.0990 | 9.492 | 0.212 | 尺度崩溃（最严重） |
| `high_1.5ms_figure8_r1` | 3.03 | 0.1592 | 3.655 | 0.211 | 尺度崩溃 |
| `low_3.0ms_circle_r1` | 2.79 | **0.6654** | 0.867 | 0.685 | 尺度偏差 + 跟踪劣化 |

## 3. 关键证据：同一 cell 的其它重复都是健康的

离群若来自光照/速度/轨迹这类**系统性因素**，同 cell 的三个重复应当一起变差。
实际不是：

| cell（light / speed / traj） | r1 | r2 | r3 |
|---|---|---|---|
| low / 1.5 / figure8 | **4.18** | 0.18 | 0.32 |
| medium / 0.5 / circle | **3.60** | 0.63 | 0.76 |
| low / 0.5 / figure8 | 1.54 | **3.55** | 0.12 |
| high / 1.5 / figure8 | **3.03** | 0.14 | 0.17 |
| low / 3.0 / circle | **2.79** | 0.62 | 0.54 |

同一个 cell 内 ATE 可以从 0.12 m 跳到 4.18 m（35 倍），而三个光照档位各自都有离群、
也各自都有健康的重复。**离群与 cell 无关，与「这一次初始化的运气」有关。**

## 4. 尺度带 × ATE 交叉表（主表 + repo54 重跑，合计 108 行）

| | ATE ≤ 1 m | ATE > 1 m |
|---|---|---|
| scale 在 `[0.96, 1.03]` 内 | **73** | **0** |
| scale 在带外 | 20 | 14 |
| 缺 scale | 1 | — |

读法：

- **尺度带内的 73 行，没有一行 ATE > 1 m** —— 精度失败与尺度失败是同一件事。
- 带外 34 行里只有 14 行 ATE>1：尺度偏一点（如 0.95、1.06）时轨迹形状还能对得上，
  ATE 仍然小；偏到 3~9 倍才彻底崩。
- 因此 **`ATE` 单指标不能作为 VINS 成败的唯一判据**，必须同时看 `sim3_scale`。

> ⚠️ `[0.96, 1.03]` 这个带是**事后硬编码**（`scripts/analysis/scale_gate.py:13`、
> `report_stats.py:24`），不是预注册阈值。宽松口径 `[0.9, 1.1]` 下通过率是 90/107。
> 写报告时必须交代口径，否则「通过率 67%」和「通过率 84%」说的不是同一件事。

## 5. 处置规则

1. **不删行**。离群行保留在原表，靠 `sim3_scale` 列做隔离，别做「清洗后的表」。
2. **统计量用中位数**，并在脚注写明 n 与剔除规则（本轮：n=54，含 5 个 ATE>2 离群）。
3. **ATE>1 m 且 scale 带外的行不参与任何均值/中位数比较**；跨 session 的绝对 ATE 一律不作对标
   （见 README「主机状态依赖」）。
4. **重跑同 cell 时用 `RUN_TAG`**，不要覆盖已有产物（`trial_one.sh` 第 8 参数）。
5. 若某 cell 三次重复**全部** ATE>1 或全部 scale 带外，才升级为「系统性失败」去查配置/场景，
   本批 18 个 cell 无一满足。

## 6. 复现

```bash
# 离群行 + 尺度
python3 scripts/analysis/scale_gate.py data/results/summary_54.csv
python3 scripts/analysis/acceptance_report.py data/results/summary_54.csv

# 只看离群 cell 的配对重跑
python3 scripts/ops/rerun_pair.py --help
```

数据出处：`data/results/summary_54.csv`、`data/results/scale_sweep.csv`、
`data/results_rerun54/paired_master_repo54.csv`。
