# 真機棋盤 ATE 重錄 SOP(2026-09-11,CHT113405)

## 目標
重錄一條棋盤全程入鏡、flow 3–5 px、HOLD 定住的序列,讓 `run_gt_ate.py`
出真機 mm 級 ATE(取代 sequence seq_real_13 的 0/198 GT)。

## 背景(seq_real_13 為何 0/198 GT)
- MOVE 平均 flow 僅 2.56 px/frame(低於甜區 3–5);HOLD0 4.79、HOLD1 3.90
  px(攝影機未真停,F7 閘門也會被吃)。
- 棋盤要全程在視野且角落數符合標定 pattern **5×4(內角)、方塊 25 mm**。

## 事前確認(30 秒)
1. ESP32 開機,連到家用 WiFi CHT113405,固定 IP **192.168.1.200**。
2. 布棋盤(5×4 內角,25 mm 方格),面正對鏡頭,距離 40–120 cm。
3. 跑自檢,確認棋盤可見:

```
python vo/chessboard_precheck.py --url http://192.168.1.200:81/stream
```
要看到 `chessboard OK: 5x4 corners, spans >=60px`。

## 錄製(1 分鐘)
```
python vo/record_clean_seq.py --url http://192.168.1.200:81/stream ^
   --seconds 6 --out vo/seq_real_14.avi
```
螢幕指引:
- HOLD0/HOLD1:徹底定住 3 秒(flow 應 <2 px)。
- MOVE:單向、連續、穩定推 6 秒,overlay 顯示 **GOOD / flow 3–5**。
  若出現「STEPWISE / TOO SLOW」調整,不要停、不要回退。

## 鏈結驗證(5 分鐘)
```
python vo/run_clean_seq_check.py --video vo/seq_real_14.avi ^
   --out-prefix vo/seq_real_14 --meta vo/seq_real_14_meta.json --min-flow 8
python vo/run_gt_ate.py --video vo/seq_real_14.avi ^
   --traj vo/seq_real_14_traj.csv --out vo/seq_real_14_ate.csv
```
注意: `--min-flow 8` 為必要參數(預設 12 會使 keyframe 數不足,
P6 12 kfs < 15 FAIL; min-flow 8 產生 18 kfs,合成 dry-run 已驗證)。
預期: `RESULT: PASS` 或至少 P1/P2/P6/P7 通過;
ATE 數值在合成基準 2.4–2.8 mm 量級(真機含標定/壓縮誤差,合理落在
<10 mm 即為閉案門檻)。

## 棋盤擺位要點
- 棋盤面**正對鏡頭**,離鏡頭 40–120 cm,偏右或偏左使它在 rig 推程中
  **全程不脫離視野**;不要把棋盤放在 rig 推進的正前方(會被推過)。
- 燈光充足、避免表面反光;棋盤平整(不要彎曲)。

## 若仍 0/198 GT
- 改 `--n-shots` 多抓幾次確認非單幀偶然。
- 把棋盤靠鏡頭、燈光打亮、表面平挺(避免反光)。
- 降低移動幅度讓棋盤不脫離視野(小推程即可,ATE 是位移精度不是里程)。