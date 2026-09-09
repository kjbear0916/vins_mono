# 乾淨序列錄製 + 驗證通過標準

目標:錄一支**單向直線平移**的真實影像序列,證明 incremental-PnP+BA
VO 的軌跡**方向正確、無跳點、無折返**,通過後才接無人機時間同步。

## 錄製(record_clean_seq.py)

三階段,MOVE 前後各一次 HOLD:
```
HOLD0 (3s, 靜止)  ->  MOVE (10~20s, 單向勻速推)  ->  HOLD1 (3s, 靜止)
```

要點:
- 相機放平移台,單向推 ~0.5–1m,中途不停、不折返
- 末端保持 2 秒以上靜止(最後 HOLD 順便當 drift 檢查)
- 現場畫面會顯示 flow,MOVE 階段單幀 flow 維持 2~15 px 最理想(太快會被
  drop 計次,太慢會讓 BA 視差不足)
- 末端 2 秒以上的畫面要自然,不要急煞

環境:
- 需先連上 ESP32 AP(避免 Windows 自動搶連外部 WiFi)
- 指令:
```
python record_clean_seq.py --url http://192.168.4.1:81/stream --seconds 15 --out vo/seq_clean_01.avi
```
- 產出:xxx.avi + xxx_meta.json(逐 phase 的 mean flow / frames / dropped)

## 通過標準(validate_traj_pass.py)

`test_incr_pnp.py --out vo/seq_clean_01_traj.csv` 產出軌跡 + `_val.json`
後,執行:
```
python validate_traj_pass.py --traj vo/seq_clean_01_traj.csv --meta vo/seq_clean_01_meta.json
```

P1 continuity  : 軌跡無 NaN/inf
P2 reproj-BA   : post-BA 誤差 <= pre-BA 且 < 5.0 px(由 _val.json)
P3 straight    : 淨位移 / 路徑長 >= 0.60(直線優先)
P4 monotonic   : 主軸前向進度最大回退 <= 25%(無折返/回溜)
P5 no jumps    : 沒有 > 5× median 的單步跳點(index 0 首步除外)
P6 structure   : >= 15 keyframes 且 >= 30 map points(_val.json)
P7 static tail : 首尾 HOLD 平均 flow < 2 px/frame(meta 判定真的靜止)
方向(報告用):主軸與位移符號,人工對照實體推的方向。

全部 >= 15 個 PASS 才進入下一階段;任一 FAIL 即重錄。

也可以一鍵跑完整流程(test_incr_pnp → 閘門 → 四合一圖):
```
python run_clean_seq_check.py --video vo/seq_clean_01.avi --out-prefix vo/seq_clean_01 --meta vo/seq_clean_01_meta.json
```
exit code 0 = 閘門全 PASS。想看圖不管 gate 結果加 `--skip-gate`。

## 合成正對照組(無硬體 regression test)

## 什麼是乾淨序列(合成正對照 + 負對照)

`gen_synth_seq.py` 用同一顆 K(QVGA 320x240、16fps)渲染完美直線平移 + 首尾
靜止,產出 schema 與錄製器相同的 avi + meta。跑完整管線期望 7/7 PASS,是
「乾淨序列長怎樣」的基準圖 `synth_clean_01_validation.png`:

```
python gen_synth_seq.py --out vo/synth_clean_01.avi
python run_clean_seq_check.py --video vo/synth_clean_01.avi --out-prefix vo/synth_clean_01 --meta vo/synth_clean_01_meta.json
```
python gen_synth_seq.py --out vo/synth_clean_01.avi
python run_clean_seq_check.py --video vo/synth_clean_01.avi --out-prefix vo/synth_clean_01 --meta vo/synth_clean_01_meta.json
```

注意:MOVE 平均 flow 須 ≥ ~3 px/frame(太低 → keyframe 太少 → P6 FAIL)。
`record_clean_seq.py` 錄影時也以「live flow 穩定維持 3~15 px」為推速指引。

## ATE 指標量測(run_gt_ate.py,需棋盤入鏡)

關閉閘門後要 mm 級精度,錄影時場景中**必須有棋盤並全程保持可見**:

- 棋盤 = 標定用同一張(calib 內的 5x4 內角點、25mm),run_gt_ate.py 會自動
  從 `calibration_esp32_qvga.npz` 讀取 pattern 與 square,不須手動填
- 棋盤佔畫面角落 ~15~25% 且不可蓋住背景特徵(<25%,否則 VO 會因特徵不足
  少產 keyframes,實測板子太大會把 kfs 從 16 砍到 5~9)
- 全程在鏡頭內、不晃動、光線均勻

同一支序列的 SOP(進 WHQF 前記得關閉 WiFi 連線以保 stream):
```
python gen_synth_seq.py --out vo/synth_gt_01.avi --board --board-grid 6x5 --board-size 6.0 --board-z 28
python run_gt_ate.py --video vo/synth_gt_01.avi --out vo/synth_gt_ate.csv
python run_gt_ate.py --video vo/seq_clean_01.avi --out vo/seq_clean_01_ate.csv
```
注意:合成棋盤必須用 `--board-grid 6x5`(內角 5x4)才會與 calib 的 pattern
相符;`gen_synth_seq.py` 內建預設是 10x7(內角 9x6),直接跑會讓
findChessboardCorners 配對失敗只剩零星 GT。
ATE 輸出行:「alignment scale(mm/unit)、ATE pre-BA / post-BA、improvement %」。

## 合成覆蓋掃描(sweep_synth.py,找閘門邊界)

`gen_synth_seq.py` 缺 `--step` 參數使 flow 無法調距,已補上。合成序列在
「無棋盤」狀態才是乾淨正對照:棋盤一入鏡(專屬測 ATE 用)會遮住中央特徵
讓 VO 退化(實測板過大 kfs 16→5–9,board-scene 軌跡 z 前向只剩 0.85)。
掃描出閘門邊界(無板正對照場景):

- **step 越小越容易 P6 FAIL**:step 0.06–0.10 全部 FAIL,主因 keyframes < 15
  (2-view init 會拖到 ~frame 50,吃掉 MOVE 配額)→ 0.16 起才穩定過
- **P3/P4 只在高 step + 高 noise 才翻**:step 0.28+ & noise 5.0+ 開始出現
  straight 0.49、retreat 7.6%(每場不一)
- **noise 越大,map pts 越多,反而更容易過 P6**(雜訊點當特徵)→ 不是 bug,
  是「特徵密度」效應,P6 門檻沒有懲罰雜訊
- 實錄對應:bundle frame 數太早 init 會吃 kfs,錄影要確認 MOVE 有真正
  parallax、不要貼牆推(會像 step=0.06 沒視差)

遍歷跑法:
```
python sweep_synth.py --steps 0.06 0.10 0.16 0.22 0.28 0.36 --noises 0.5 1.5 3.0 5.0 8.0
```
產出:vo/_cov/<tag>.avi+traj+meta(取樣保留)、vo/_cov/sweep_summary.csv

## 錄影前:ESP32 preflight(必做)

韌體預設「運動偵測 + 拍照閃光燈」會在被推時觸發並燒壞 stream —— 錄製前
必須關閉並鎖定 QVGA 手動曝光:
```
python esp32_cam_server/preflight_esp32.py --url http://192.168.4.1
```
會自動:關 motion_enabled/capture_on_motion → 強制 framesize=QVGA(5) →
手動曝光(aec=0, aec_value=500) → stream 解碼 3 幀驗證。通過印
「PREFLIGHT PASSED -- ready to record VO sequence」才開始錄。
(不加參數 = 只檢查並回報現況)

## 負對照(2026-09-09,gen_synth_seq --motion)

驗證 7 閘門對「壞運動」會正確 FAIL。`gen_synth_seq.py --motion {straight|
back_forth|jump|curve}`;step 0.16 / noise 1.5 / 與正對照同參數。

| motion | P3 straight | P4 monotonic | P5 | P6 kfs | RESULT |
|---|---|---|---|---|---|---|
| straight | 0.92 | 0% | 0 jumps | 16 | **PASS** |
| back_forth | 0.06 | 88.7% | 0 | 13 | **FAIL**(P3+P4,精準) |
| jump(3x×5幀) | 0.90 | 0% | 0 | 14 | **FAIL**(P6) |
| curve(側移弧) | 0.82 | 4% | 0 | 18 | **PASS**(太直,緩弧不該被拒) |
| hold_jitter(0.25) | — | — | — | — | **FAIL**(P7,HOLD flow 10.4/18.6 px >2) |

發現:
- 折返命中 P3/P4,是設計要抓的典型壞運動。
- **跳躍/緩弧不會觸發 P5/P3**:暴衝段 LK 追蹤先斷 → 軌跡被 VO 展開成多段
  kf(max step 只 ~1.8×median),P5 看單步不外刺;緩弧 net/path 0.82 ≥0.6。
  對 P5/P3 的「偵測極限」是有意的保守(不誤殺輕微不直),實錄惡化需靠
  HOLD0/HOLD1 前後比對。
- jump 追蹤受損 → kfs 14 仍 FAIL(P6),所以壞運動不會全綠,只是落在不同閘門。
- **P7 負對照(2026-09-09)**:`gen_synth_seq.py --hold-jitter <amt>` 在 HOLD 段
  疊加隨機平移,meta 才真的算出 HOLD mean flow。jitter=0.25 時
  HOLD0 10.4 / HOLD1 18.6 px>2px → **P7 正確 FAIL**。這是 7 閘門中唯一先前
  沒有負對照的(合成一直 no-meta,靠權宜繞過),現在補齊。
  注意:jitter 是加入 `t_wc` 的隨機 walk,HOLD 的 mean flow 需
  `gen_synth_seq` 的 meta 寫入才讀得到(改版前 meta 只對非 None step 算 flow,
  HOLD 恆顯示 0.00 → P7 永遠假 PASS)。

## run_gt_ate.py:`--traj` 是強制參數(不再內建重跑 VO)

`run_gt_ate.py` **不再自己重跑 VO**。class `IncrementalPnpVO` 與閘門 script
的 `MIN_FLOW` 行為不一致(實測同樣輸入 class 只產 2~13 kfs 而 script 產 16),
原本 fallback 會悄悄產出無效 ATE;現在 `--traj` 是 required,少了就報錯。
吃 `test_incr_pnp.py` 的 `*_traj.csv`(閘門同一條軌跡):
```
python run_clean_seq_check.py --video vo/seq_xxx.avi --out-prefix vo/seq_xxx
python run_gt_ate.py --video vo/seq_xxx.avi --traj vo/seq_xxx_traj.csv --out vo/seq_xxx_ate.csv
```
自動從 calib 讀 board pattern(5x4)+square,只對「既有 kf 幀且偵到棋盤」的
幀算 ATE,pre 與 post 用 CSV 內的中心值(不再產生第二套 BA)。
VO 的 pre/post 中心都來自 `test_incr_pnp` 的 BA——ATE 評估的就是閘門那條軌跡。

## 過往資料狀態(2026-09-09)

- real_seq.avi(replay 用):FAIL(P3=0.21、P4 回退 54%、9 跳點、末端追蹤崩)-> 只適合 run_incr_pnp.py 除錯,不適合作 GT 驗證
- 2026-09-09(ate 修正):`run_gt_ate.umeyama_sim3` 原本 **R=Vt^T·S·U^T 寫反成 U·S·Vt 且 scale 誤除 (n-1)**,導致所有 ATE 數值(含先前 416mm 等)不可信;已修正並加 `test_regression.py` 10 項 unittest(含相似形恢復、center_of、閘門正/負對照、drone_sync align)— `python -m unittest vo/test_regression.py -v` 一鍵驗證
- run_gt_ate 新增 `--traj` 路徑:吃官方 `test_incr_pnp` 的 `*_traj.csv`,不再自己重跑 class VO(與閘門管線 `MIN_FLOW` 行為不一致,導致 2~13 kfs)。
- **umeyama 修復後 harness 翻 PASS**:`test_ate_harness.py`(官方管線 + 已知合成真值)從「main scale 2030 / ATE 64mm / FAIL」變成「scale 91.6(match 92x VO scale)/ ATE pre 0.90 → post 0.71 mm,improvement 21% / PASS」。ATE bootstrap 現在通行。
- `_cov/sweep_summary.csv` 的 6 行 board ATE 先前全部標 **INVALID(obs 0005)** — buggy umeyama 產的 pre==post 假象。**已重算**:`sweep_synth.py` 的 board 分支改用官方管線 `test_incr_pnp --traj`(不再走會退化的 class VO fallback),板配置改為近距小板(z 10~14),6 個組合全部拿到 **GT∩kf=5、可信 mm ATE**:
  - b_z10_n15: pre 3.32 → post 2.47 mm
  - b_z10_n50: pre 7.00 → post 2.40 mm
  - b_z12_n15: pre 11.05 → post 10.78 mm(z12 GT 偵測較差)
  - b_z12_n50: pre 3.06 → post 2.76 mm
  - b_z14_n15: pre 3.00 → post 2.43 mm
  - b_z14_n50: pre 2.76 → post 2.47 mm
  結論:修復後 umeyama 之下 post-BA 穩定落在 2.4~2.8 mm(除 z12_n15),與 harness 的 0.7mm 同量級;遠板(z24~32)無法維持 GT∩kf≥4,已從矩陣移除。
- 2026-09-09:**run_gt_ate 移除所有內建 VO fallback**,`--traj` 變成強制參數
  (class/localmap VO 重跑路徑整個刪除,不再有「悄悄用 2 kfs 的 drift VO 算
  ATE」的可能)。sweep 與 harness 先前已全部走 `--traj` 路徑,此改動不影響
  既有結果。**`vo_incr_pnp.py`(class `IncrementalPnpVO`)因失去所有生產消費
  者而整檔刪除**,官方管線 `test_incr_pnp.py` 是唯一的軌跡來源;regression
  的 drift 監測測試改為純「官方 script keyframe 量」健康檢查。
- 2026-09-09 sweep:修正 gen_synth_seq.py 支援 --step;新增 sweep_synth.py;
  發現 run_gt_ate.py 對齊 bug(keyframe slot 索引錯位,已修:lm.Rs 依 kf 序
  而 idk 是 frame 號);合成板需 6x5 grid 才匹配 5x4 pattern
- 重錄後生效;此標準由 validate_traj_pass.py 自動檢核,結束碼 0/1=PASS/FAIL