# API 文檔

鼠患智能監控系統的 HTTP API 介面。

## 基礎資訊

- **Base URL**：`http://[ESP32_IP]`
- **預設端口**：80（Web/API）、81（串流）
- **內容類型**：`application/json`（JSON 回應）

## 端點列表

### 系統端點

#### GET `/status`
取得系統狀態。

**回應範例**：
```json
{
  "framesize": 10,
  "quality": 10,
  "brightness": -2,
  "contrast": 2,
  "saturation": -2,
  "sharpness": 0,
  "special_effect": 0,
  "wb_mode": 0,
  "awb": 1,
  "aec": 0,
  "aec_value": 500,
  "agc": 1,
  "hmirror": 0,
  "vflip": 1,
  "dcw": 1,
  "colorbar": 0,
  "xclk": 20,
  "pixformat": 5,
  "led_intensity": 0
}
```

#### GET `/capture`
拍攝一張照片並返回 JPEG。

**回應**：
- `Content-Type: image/jpeg`
- `Content-Disposition: inline; filename=capture.jpg`
- `X-Timestamp`: 拍攝時間戳記

#### GET `/stream`
MJPEG 即時影像串流。

**回應**：`multipart/x-mixed-replace; boundary=...`

#### GET `/bmp`
拍攝並轉換為 BMP 格式（不建議用於網頁，僅供調試）。

### 攝影機控制端點

#### GET `/control?var=xxx&val=yyy`
設定攝影機參數。

**參數**：

| 變數 | 類型 | 範圍 | 說明 |
|------|------|------|------|
| framesize | int | 0-13 | 解析度 |
| quality | int | 0-63 | JPEG 品質（越低越好） |
| contrast | int | -2到2 | 對比度 |
| brightness | int | -2到2 | 亮度 |
| saturation | int | -2到2 | 飽和度 |
| gainceiling | int | 0-6 | 增益上限 |
| colorbar | int | 0/1 | 顏色條測試 |
| awb | int | 0/1 | 自動白平衡 |
| agc | int | 0/1 | 自動增益控制 |
| aec | int | 0/1 | 自動曝光控制 |
| aec_value | int | 0-1200 | 曝光值 |
| hmirror | int | 0/1 | 水平翻轉 |
| vflip | int | 0/1 | 垂直翻轉 |
| led_intensity | int | 0-255 | LED 亮度 |

**範例**：
```
GET /control?var=framesize&val=11
GET /control?var=vflip&val=1
GET /control?var=led_intensity&val=200
```

#### GET `/xclk?xclk=20`
設定 XCLK 頻率（MHz）。

#### GET `/reg?reg=0x00&mask=0xFF&val=0x01`
直接寫入感測器暫存器。

#### GET `/greg?reg=0x00&mask=0xFF`
讀取感測器暫存器。

#### GET `/resolution?sx=0&sy=0&ex=640&ey=480`
設定感測器視窗解析度。

### 系統管理端點

#### GET `/config?key=xxx`
取得設定值。

#### POST `/config?key=xxx&value=yyy`
設定配置並保存到 NVS。

**可用 Key**：

| Key | 類型 | 說明 |
|-----|------|------|
| wifi_ssid | string | WiFi 名稱 |
| wifi_password | string | WiFi 密碼 |
| motion_enabled | bool | 運動偵測開關 |
| motion_sensitivity | int | 靈敏度 (1-100) |
| motion_cooldown | int | 冷卻時間 (ms) |
| pir_enabled | bool | PIR 感測器開關 |
| alert_enabled | bool | 告警系統開關 |
| telegram_enabled | bool | Telegram 通知開關 |
| telegram_token | string | Bot Token |
| telegram_chat_id | string | Chat ID |
| email_enabled | bool | Email 通知開關 |
| sd_enabled | bool | SD 卡儲存開關 |
| ntp_enabled | bool | 時間同步開關 |

#### GET `/events`
取得事件日誌。

**回應範例**：
```json
{
  "events": [
    {"type": 1, "ts": 1628000000, "level": 0, "desc": "Motion detected"},
    {"type": 2, "ts": 1628000005, "level": 0, "desc": "Image captured"}
  ],
  "stats": {"total": 2, "motion": 1, "errors": 0, "alerts": 0}
}
```

#### GET `/events?clear=1`
清除事件日誌。

#### GET `/sd/status`
取得 SD 卡狀態。

**回應範例**：
```json
{
  "mounted": true,
  "total": 31914983424,
  "used": 10485760,
  "free": 31904497664,
  "file_count": 42
}
```

#### GET `/sd/images`
取得 SD 卡影像列表。

#### GET `/sd/images?file=xxx.jpg`
下載指定影像（或刪除：`?delete=1`）。

#### POST `/sd/clear`
清除 SD 卡所有影像。

#### GET `/test/telegram`
測試 Telegram 連接（發送測試訊息）。

#### GET `/restart`
重新啟動設備。

#### POST `/reset`
恢復出廠設定。

## 錯誤處理

所有錯誤回應使用 HTTP 狀態碼：

| 狀態碼 | 說明 |
|--------|------|
| 200 | 成功 |
| 400 | 請求錯誤（缺少參數） |
| 404 | 資源不存在 / 參數錯誤 |
| 500 | 內部錯誤 |

錯誤回應格式：
```json
{
  "error": "description"
}
```

## 速率限制

- 暫無速率限制
- 但過快的請求可能導致效能下降
- 建議拍照間隔至少 1 秒

## 安全注意事項

> **警告**：此系統沒有內建驗證機制。請注意以下事項：
> - 不要直接暴露在公共網路上
> - 使用 VPN 或防火牆保護
> - 如需遠端訪問，建議使用反向代理加認證
> - WiFi 密碼建議使用 WPA2/WPA3
