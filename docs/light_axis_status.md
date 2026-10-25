# 光照轴状态核查：从「标签无效」到「已接线但非单变量」

> 本文替代 README 里 2026-10-11 的那段「光照轴实际未生效」结论。
> 三段历史必须分开看，混为一谈会得出错误结论：
>
> | 阶段 | 日期 | 光照轴是否真的切换了世界 | 结果能不能归因于光照 |
> |---|---|---|---|
> | 主表 54 组（`data/results/summary_54.csv`） | 2026-10-09~10 | ❌ 否，三档都跑 `vins_demo.world` | ❌ 不能（三档是同条件重复） |
> | lfinal 54 组（`data/results_light_final/summary_54.csv`） | 2026-10-12 | ✅ 是，`light_*.world` 真的加载了 | ❌ 仍不能（世界文件的**几何**也变了） |

**一句话结论**：光照轴已经不再是空标签，但 `light_*.world` 与主表用的 `vins_demo.world`
差的不只是 `<scene>/<light>`，还多了 12 个塔状遮挡物，所以 lfinal 矩阵是
「光照 × 几何 × 主机状态」的混合效应，**不能用来支持「光照变暗 → 精度下降」这类结论**。

---

## 1. 证据 A：光照轴确实已经生效

`scripts/ops/trial_one.sh`（md5 `384325554b12da942bb52f6b03695484`）第 16–25 行：

```bash
# Light axis (fix): LIGHT (arg 1) selects the world file so the three arms run
# genuinely different scenes. Before this, LIGHT was only a label and every arm
# ran vins_demo, leaving the light axis silently inert. An explicit VINS_WORLD
# ...
case "$LIGHT" in
  high|medium|low) _def_world="light_${LIGHT}" ;;
...
VINS_WORLD=${VINS_WORLD:-$_def_world}
export VINS_WORLD
```

产物端的旁证（`data/results_light_final/trial_high_0.5ms_circle_r1_lfinal/manifest.json`）：

```json
"vins_world": "light_high",
"md5": {
  "worlds/light_high.world":     "3d2c520bb7e4a14ab92d02de086cad31",
  "px4_world/light_high.world":  "87468ab89608002f0c3f4544b5695d8b"
}
```

`vins_world` 字段不再恒为 `vins_demo`，而且 manifest 同时记下了**两份 md5 不同的**
`light_high.world` —— 这正是下面第 3 节要处理的问题。

## 2. 证据 B：lfinal 全矩阵结果

54/54 完成、`features_note` 全为 `ok`，基础设施健康：

| 指标 | 值 |
|---|---|
| wall_s 中位（min–max） | 189 s（173–207） |
| RTF 中位（min–max） | 0.465（0.433–0.514） |
| IMU 实测中位 | 50.01 Hz（50.00–50.61） |

按光照分档（ATE_RMS = `evo_ape` 的 RMSE，单位 m）：

| 光照 | n | ATE 中位 | ATE>1 m | 最大值 | RPE 中位 |
|---|---|---|---|---|---|
| high | 18 | **1.160** | 11/18 | 1.87 | 0.0354 |
| medium | 18 | **1.676** | 17/18 | 7.03 | 0.0676 |
| low | 18 | **1.492** | 15/18 | 9.82 | 0.0417 |
| 全体 | 54 | **1.390** | **43/54** | 9.82 | — |

对照主表（光照未生效的那一批）：全体中位 **0.365 m**，ATE>1 仅 5/54。

读法：

1. **三档全部劣化到 ATE>1 量级**，没有「越暗越差」的单调关系；
2. **high 档也坏**（中位 1.160 m，11/18 超 1 m）—— 如果劣化来自照度，最亮的一档应当最接近主表；
3. RTF 也从主表的 ~0.55 降到 0.465，说明渲染负载变重了 —— 与「场景里多了几何体」一致，
   而不是「图更暗」。
4. medium 反而比 low 更差，档位之间没有可解释的排序。

## 3. 证据 C：三份世界文件互不一致（根因）

同名世界文件在仓库里有三处，内容各不相同：

| 位置 | 用途 | `<scene>`/`<light>` | `ground_plane`/`sun` | 塔（`towers`） | 大小 |
|---|---|---|---|---|---|
| `docker/assets/vins_demo.world` | 主表 54 组实际加载 | 默认 | ✅ 有 | ❌ 无 | 1.1 KB |
| `docker/assets/light_*.world` | **lfinal 54 组实际加载** | ✅ 自定义 ambient/background/sun | ❌ 无（只有 asphalt_plane） | ✅ **12 个**（t0–t11，1.2–2 m 见方、5–9 m 高） | 3.8 KB |
| `worlds/light_*.world` | 仓库内参考副本，不被 `setup_sim_assets.sh` 安装 | ✅ 自定义 | ❌ 无 | ❌ 无 | 1.5 KB |

`light_*.world` 与 `vins_demo.world` 的结构差异（`Compare-Object`，剔除光照行后）：

```
=> <model name='towers'>        ... t0..t11，Gazebo/Red|Green|Blue|Yellow|Cyan|Purple|Grey|DarkGreen...
```

即：**lfinal 的「光照臂」同时改变了场景几何与特征分布**。塔是强纹理、强遮挡物，
对 VINS 的特征跟踪与初始化影响远大于环境光强度，这是 lfinal 全体劣化最可能的解释。

另外，`setup_sim_assets.sh` 只安装 `docker/assets/` 下的世界文件（第 63–79 行），
所以 `worlds/light_*.world` 这份「看起来更干净」的副本（无塔）其实**从未参与任何实验**。

## 4. 禁止的推论

以下四句话都不成立，任何后续报告/答辩都不要写：

- ❌「光照越暗，VINS 的 ATE 越大」—— lfinal 三档无单调关系，且 high 也失败。
- ❌「真实光照条件下 ATE 从 0.365 m 恶化到 1.39 m」—— 两个矩阵的场景、几何都不同，不可比。
- ❌「low 档失败率 15/18，说明低照度是主因」—— 几何混杂未排除。
- ❌「光照轴已验证无影响」—— 主表那一批从未真正切换光照，属于「未测」而非「无影响」。

可以写的只有：

- ✅「光照轴在 2026-10-12 前是失效的，之前的逐光照差异来自运行间随机性/主机状态。」
- ✅「第一次真正切换世界的矩阵（lfinal）出现全体劣化，已定位到世界文件几何不一致，
  修复前的数据不支持任何光照结论。」

## 5. 要做成干净的单变量光照实验

按顺序做完，缺一项结论就仍不可用：

1. **统一几何**：令 `light_*.world` 与 `vins_demo.world` 除 `<scene>`（ambient/background/shadows）
   与 `<light>`（diffuse/specular/direction）外逐行相同。二选一：
   - 删掉 `light_*` 里的 `towers` 模型（与主表对齐，推荐 —— 主表是已发表的主结果）；
   - 或把 `towers` 同时加进 `vins_demo.world` 并重跑主表（工作量大，且会让已有主表失效）。
2. **消除副本分叉**：`worlds/light_*.world` 与 `docker/assets/light_*.world` 合并成一份
   （建议只保留 `docker/assets/`，因为 `setup_sim_assets.sh` 只认它；`worlds/` 那份要么同步、
   要么删除，否则下次核查还会踩同一个坑）。
3. **加 preflight 断言**：跑矩阵前 diff 三个 world，只允许 `<scene>`/`<light>` 行不同；
   或直接断言三个文件的行数一致、且 `grep -c "model name='towers'"` 三者一致。
4. **记录特征数**：manifest 里补 `features_n`（VINS 日志的 `feature_tracker` 数量），
   否则无法区分「照度导致特征减少」与「场景换了」。
5. **同会话配对**：lfinal 与主表跨 session，绝对 ATE 不可比（见 README 的「主机状态依赖」）。
   干净的做法是在**同一次会话内**跑 3 档 × 3 rep 的 `circle/1.5`，只比配对的差分。
6. **重跑并换 tag**：`RUN_TAG=lightonly`，不要覆盖 `lfinal`（保留这次的反面证据）。

## 6. 复现命令

```bash
# 单档验证（改完 world 之后先跑 3 次确认高光档不再劣化）
bash scripts/ops/trial_one.sh high circle 1.5 5.0 3.0 45 1 lightonly

# 全矩阵
python3 scripts/ops/batch_run_54.py            # RUN_TAG 由 batch_run_54.py 传入
bash scripts/evaluation/evaluate_all.sh /data/rosbags /data/results_lightonly sim_1.5ms_circle_r1
python3 scripts/analysis/scale_gate.py data/results_lightonly/summary_54.csv
```

## 7. 数据出处

- lfinal 汇总：`data/results_light_final/summary_54.csv`（已入库，54 行 + 表头）
- lfinal 运行日志：`data/results_light_final/run.log`（已入库，含每 trial 的 exit/timeout/ATE）
- 主表汇总：`data/results/summary_54.csv`
- 世界文件：`docker/assets/vins_demo.world`、`docker/assets/light_{high,medium,low}.world`、
  `worlds/light_{high,medium,low}.world`
- 安装逻辑：`docker/setup_sim_assets.sh` 第 63–79 行
