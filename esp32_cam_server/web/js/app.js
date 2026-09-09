// ==========================================
// 鼠患智能監控系統 - Web 介面腳本
// ==========================================

// ========== 全域變數 ==========
const API_BASE = window.location.origin;
let isStreaming = false;
let streamRetryCount = 0;
const MAX_STREAM_RETRY = 5;
let lastFrameTime = 0;
let fps = 0;
let currentTab = 'camera';
let eventRefreshTimer = null;

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    startVideoStream();
    loadSystemStatus();
    refreshEvents();
    
    // 定時重新整理狀態
    setInterval(loadSystemStatus, 10000);
    setInterval(refreshEvents, 30000);
    
    // 綁定全螢幕按鈕
    document.getElementById('fullscreenBtn').addEventListener('click', toggleFullscreen);
    
    // 綁定拍照按鈕
    document.getElementById('captureBtn').addEventListener('click', capturePhoto);
});

// ========== 標籤頁 ==========
function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            // 切換標籤高亮
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // 切換內容
            currentTab = tab.dataset.tab;
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(currentTab + 'Tab').classList.add('active');
            
            // 載入對應設定
            loadTabSettings(currentTab);
        });
    });
}

// 載入標籤頁設定
function loadTabSettings(tab) {
    switch(tab) {
        case 'camera':
            loadCameraSettings();
            break;
        case 'motion':
            loadMotionSettings();
            break;
        case 'alerts':
            loadAlertSettings();
            break;
        case 'storage':
            loadStorageSettings();
            break;
        case 'system':
            loadSystemSettings();
            break;
    }
}

// ========== 影像串流 ==========
function startVideoStream() {
    const img = document.getElementById('videoStream');
    const overlay = document.getElementById('videoOverlay');
    
    // 設定串流 URL
    const streamUrl = `${API_BASE}/stream`;
    
    // 使用時間戳來避免緩存
    img.src = `${streamUrl}?t=${Date.now()}`;
    
    img.onload = () => {
        overlay.classList.add('hidden');
        isStreaming = true;
        streamRetryCount = 0;
        
        // 計算 FPS
        const now = performance.now();
        if (lastFrameTime > 0) {
            const delta = now - lastFrameTime;
            if (delta > 0) {
                fps = Math.round(1000 / delta);
                updateFPS();
            }
        }
        lastFrameTime = now;
        
        updateConnectionStatus('online', '線上');
    };
    
    img.onerror = () => {
        overlay.classList.remove('hidden');
        overlay.textContent = '影像連線中斷';
        isStreaming = false;
        
        if (streamRetryCount < MAX_STREAM_RETRY) {
            streamRetryCount++;
            updateConnectionStatus('connecting', `重連中 (${streamRetryCount})...`);
            setTimeout(startVideoStream, 3000);
        } else {
            updateConnectionStatus('offline', '離線');
        }
    };
}

// 更新 FPS 顯示
function updateFPS() {
    const fpsEl = document.getElementById('fpsInfo');
    if (fpsEl) {
        fpsEl.textContent = `FPS: ${fps}`;
        // 彩色顯示
        fpsEl.style.color = fps >= 15 ? '#10b981' : (fps >= 5 ? '#f59e0b' : '#ef4444');
    }
}

// ========== 系統狀態 ==========
async function loadSystemStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        if (!response.ok) return;
        
        const data = await response.json();
        
        // 更新攝影機狀態
        updateCameraStatusFromStatus(data);
        updateConnectionStatus('online', '線上');
        
        // 更新系統資訊
        updateSystemInfo(data);
        
    } catch (error) {
        console.error('Failed to load status:', error);
        updateConnectionStatus('offline', '離線');
    }
}

function updateCameraStatusFromStatus(data) {
    // 更新攝影機設定顯示
    if (data.framesize !== undefined) {
        document.getElementById('framesize').value = data.framesize;
    }
    if (data.quality !== undefined) {
        document.getElementById('quality').value = data.quality;
        document.getElementById('qualityValue').textContent = data.quality;
    }
    if (data.brightness !== undefined) {
        document.getElementById('brightness').value = data.brightness;
        document.getElementById('brightnessValue').textContent = data.brightness;
    }
    if (data.contrast !== undefined) {
        document.getElementById('contrast').value = data.contrast;
        document.getElementById('contrastValue').textContent = data.contrast;
    }
    if (data.saturation !== undefined) {
        document.getElementById('saturation').value = data.saturation;
        document.getElementById('saturationValue').textContent = data.saturation;
    }
    if (data.hmirror !== undefined) {
        document.getElementById('hmirror').checked = data.hmirror === 1;
    }
    if (data.vflip !== undefined) {
        document.getElementById('vflip').checked = data.vflip === 1;
    }
    
    // 更新解析度
    const resolutions = {
        9: 'UXGA 1600x1200',
        10: 'SVGA 800x600',
        11: 'VGA 640x480',
        13: 'QVGA 320x240'
    };
    if (data.framesize !== undefined) {
        document.getElementById('resolutionInfo').textContent = 
            `解析度: ${resolutions[data.framesize] || '未知'}`;
    }
}

function updateSystemInfo(data) {
    // IP 位址
    if (data.ip && document.getElementById('sysIP')) {
        document.getElementById('sysIP').textContent = data.ip;
    }
    
    // 系統名稱
    if (data.system_name && document.getElementById('sysName')) {
        document.getElementById('sysName').textContent = data.system_name;
    }
    
    // 版本
    if (data.version && document.getElementById('sysVersion')) {
        document.getElementById('sysVersion').textContent = data.version;
    }
    
    // 運行時間
    if (data.uptime && document.getElementById('uptime')) {
        document.getElementById('uptime').textContent = formatUptime(data.uptime);
    }
    
    // WiFi 訊號
    if (data.rssi !== undefined && document.getElementById('wifiSignal')) {
        const rssi = data.rssi;
        let quality = '很弱';
        if (rssi >= -50) quality = '極佳';
        else if (rssi >= -60) quality = '良好';
        else if (rssi >= -70) quality = '普通';
        else if (rssi >= -80) quality = '微弱';
        document.getElementById('wifiSignal').textContent = `${quality} (${rssi}dBm)`;
    }
    
    // 記憶體
    if (data.free_heap !== undefined && document.getElementById('freeHeap')) {
        document.getElementById('freeHeap').textContent = 
            `${(data.free_heap / 1024).toFixed(1)} KB`;
    }
    
    // 更新品質顯示
    if (data.quality !== undefined) {
        document.getElementById('qualityInfo').textContent = `品質: ${data.quality}`;
    }
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) return `${days}天 ${hours}小時`;
    if (hours > 0) return `${hours}小時 ${minutes}分`;
    return `${minutes}分鐘`;
}

// ========== 連接狀態 ==========
function updateConnectionStatus(status, text) {
    const indicator = document.getElementById('connectionStatus');
    indicator.className = `status-indicator ${status}`;
    document.getElementById('statusText').textContent = text;
}

// ========== 拍照 ==========
async function capturePhoto() {
    const btn = document.getElementById('captureBtn');
    btn.disabled = true;
    btn.textContent = '📸 拍照中...';
    
    try {
        const response = await fetch(`${API_BASE}/capture`, { method: 'GET' });
        if (!response.ok) throw new Error('Capture failed');
        
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        
        // 顯示照片
        document.getElementById('capturedImage').src = url;
        document.getElementById('downloadLink').href = url;
        document.getElementById('downloadLink').download = `capture_${Date.now()}.jpg`;
        document.getElementById('captureInfo').textContent = 
            `${(blob.size / 1024).toFixed(1)} KB - ${new Date().toLocaleTimeString()}`;
        
        openModal();
        showToast('照片拍攝成功', 'success');
        
    } catch (error) {
        console.error('Capture error:', error);
        showToast('拍照失敗', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '📸 拍照';
    }
}

// ========== 快顯視窗 ==========
function openModal() {
    document.getElementById('captureModal').classList.add('open');
}

function closeModal() {
    document.getElementById('captureModal').classList.remove('open');
}

document.getElementById('captureModal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
        closeModal();
    }
});

// ========== 全螢幕 ==========
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
    } else {
        document.exitFullscreen();
    }
}

// ========== 攝影機設定 ==========
async function applyCameraSetting(variable, value) {
    try {
        const response = await fetch(
            `${API_BASE}/control?var=${variable}&val=${value}&t=${Date.now()}`
        );
        if (response.ok) {
            showToast('設定已套用', 'success');
            console.log(`[Camera] ${variable} = ${value}`);
        } else {
            showToast('套用失敗', 'error');
        }
    } catch (error) {
        console.error('Apply setting failed:', error);
        showToast('設定失敗', 'error');
    }
}

function loadCameraSettings() {
    // 狀態載入已經更新了這些設定
}

// ========== 運動偵測設定 ==========
function loadMotionSettings() {
    // 從設定 API 載入
    fetch(`${API_BASE}/config?key=motion_enabled`)
        .then(r => r.text())
        .then(val => {
            document.getElementById('motionEnabled').checked = val === '1' || val === 'true';
        })
        .catch(() => {});
        
    fetch(`${API_BASE}/config?key=motion_sensitivity`)
        .then(r => r.text())
        .then(val => {
            if (val) {
                document.getElementById('motionSensitivity').value = parseInt(val);
                document.getElementById('motionSensitivityValue').textContent = val;
            }
        })
        .catch(() => {});
}

// ========== 告警設定 ==========
function loadAlertSettings() {
    // 載入各項設定
    const settings = ['alert_enabled', 'telegram_enabled', 'email_enabled'];
    
    settings.forEach(key => {
        fetch(`${API_BASE}/config?key=${key}`)
            .then(r => r.text())
            .then(val => {
                const el = document.getElementById(mapKeyToId(key));
                if (el) {
                    el.checked = val === '1' || val === 'true';
                }
            })
            .catch(() => {});
    });
}

function mapKeyToId(key) {
    const map = {
        'alert_enabled': 'alertEnabled',
        'telegram_enabled': 'telegramEnabled',
        'email_enabled': 'emailEnabled'
    };
    return map[key] || key;
}

async function saveTelegramConfig() {
    const token = document.getElementById('telegramToken').value;
    const chatId = document.getElementById('telegramChatId').value;
    
    if (!token || !chatId) {
        showToast('請輸入 Bot Token 和 Chat ID', 'warning');
        return;
    }
    
    try {
        // 儲存設定
        await saveSetting('telegram_token', encodeURIComponent(token));
        await saveSetting('telegram_chat_id', encodeURIComponent(chatId));
        showToast('Telegram 設定已儲存', 'success');
    } catch (error) {
        showToast('儲存失敗', 'error');
    }
}

async function saveEmailConfig() {
    const recipient = document.getElementById('emailRecipient').value;
    
    if (!recipient) {
        showToast('請輸入收件信箱', 'warning');
        return;
    }
    
    try {
        await saveSetting('email_recipient', encodeURIComponent(recipient));
        showToast('Email 設定已儲存', 'success');
    } catch (error) {
        showToast('儲存失敗', 'error');
    }
}

async function testTelegram() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '📤 發送中...';
    
    try {
        const response = await fetch(`${API_BASE}/test/telegram`);
        const result = await response.text();
        
        if (result.includes('success') || result === 'OK') {
            showToast('Telegram 測試訊息已發送', 'success');
        } else {
            showToast('發送失敗，請檢查設定', 'error');
        }
    } catch (error) {
        showToast('發送失敗', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '📤 測試發送';
    }
}

// ========== 儲存設定 ==========
function loadStorageSettings() {
    // 從狀態 API 獲取 SD 卡資訊
    fetch(`${API_BASE}/sd/status`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('sdStatus').textContent = 
                data.mounted ? '正常' : '未連接';
            document.getElementById('sdStatus').style.color = 
                data.mounted ? '#10b981' : '#ef4444';
            document.getElementById('sdFreeSpace').textContent = 
                data.free ? formatBytes(data.free) : '--';
            document.getElementById('sdFileCount').textContent = 
                data.file_count || 0;
        })
        .catch(() => {
            document.getElementById('sdStatus').textContent = '無法讀取';
        });
}

function formatBytes(bytes) {
    if (bytes >= 1024 * 1024 * 1024) {
        return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
    } else if (bytes >= 1024 * 1024) {
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    } else {
        return `${bytes} B`;
    }
}

async function clearAllImages() {
    if (!confirm('確定要清除所有影像嗎？此操作無法復原。')) return;
    
    try {
        const response = await fetch(`${API_BASE}/sd/clear`);
        showToast('影像已清除', 'success');
        loadStorageSettings();
    } catch (error) {
        showToast('清除失敗', 'error');
    }
}

async function formatSD() {
    if (!confirm('確定要格式化 SD 卡嗎？所有資料將被刪除！')) return;
    
    try {
        const response = await fetch(`${API_BASE}/sd/format`);
        showToast('SD 卡已格式化', 'success');
        loadStorageSettings();
    } catch (error) {
        showToast('格式化失敗', 'error');
    }
}

// ========== 系統設定 ==========
function loadSystemSettings() {
    // 已由 loadSystemStatus 更新
}

async function restartDevice() {
    if (!confirm('確定要重新啟動設備嗎？')) return;
    
    try {
        await fetch(`${API_BASE}/restart`);
        showToast('正在重新啟動...', 'warning');
        
        // 等待設備重啟
        setTimeout(() => {
            updateConnectionStatus('connecting', '等待重新連線...');
            setTimeout(startVideoStream, 5000);
        }, 3000);
    } catch (error) {
        // 設備重啟後連接會中斷，這是正常的
        setTimeout(() => {
            updateConnectionStatus('connecting', '等待重新連線...');
            setTimeout(startVideoStream, 5000);
        }, 3000);
    }
}

async function resetConfig() {
    if (!confirm('確定要恢復出廠設定嗎？所有設定將被清除！')) return;
    
    try {
        const response = await fetch(`${API_BASE}/reset`, { method: 'POST' });
        if (response.ok) {
            showToast('設定已重置，設備將重新啟動', 'success');
            setTimeout(restartDevice, 1000);
        } else {
            showToast('重置失敗', 'error');
        }
    } catch (error) {
        showToast('重置失敗', 'error');
    }
}

// ========== 通用設定儲存 ==========
async function saveSetting(key, value) {
    try {
        const response = await fetch(
            `${API_BASE}/config?key=${encodeURIComponent(key)}&value=${encodeURIComponent(value)}&t=${Date.now()}`,
            { method: 'POST' }
        );
        
        if (response.ok) {
            showToast(`${key} 設定已儲存`, 'success');
            return true;
        } else {
            showToast('儲存失敗', 'error');
            return false;
        }
    } catch (error) {
        console.error('Save setting failed:', error);
        showToast('儲存失敗', 'error');
        return false;
    }
}

// ========== 事件日誌 ==========
async function refreshEvents() {
    try {
        const response = await fetch(`${API_BASE}/events`);
        if (!response.ok) return;
        
        const data = await response.json();
        renderEvents(data);
    } catch (error) {
        console.error('Failed to load events:', error);
    }
}

function renderEvents(data) {
    const list = document.getElementById('eventList');
    
    if (!data.events || data.events.length === 0) {
        list.innerHTML = '<div class="event-item empty">尚無事件記錄</div>';
        return;
    }
    
    let html = '';
    data.events.forEach(event => {
        const icon = getEventIcon(event.type);
        const className = getEventClass(event.level);
        const time = formatEventTime(event.ts);
        
        html += `
            <div class="event-item ${className}">
                <span class="icon">${icon}</span>
                <span class="time">${time}</span>
                <span class="message">${escapeHtml(event.desc)}</span>
            </div>
        `;
    });
    
    list.innerHTML = html;
}

function getEventIcon(type) {
    const icons = {
        0: '🔄',  // SYSTEM_START
        1: '🐭',  // MOTION_DETECTED
        2: '📸',  // IMAGE_CAPTURED
        3: '🔔',  // ALERT_SENT
        4: '📶',  // WIFI_CONNECTED
        5: '⚠️',  // WIFI_DISCONNECTED
        6: '💾',  // SD_MOUNTED
        7: '❌',  // SD_ERROR
        8: '🕐',  // NTP_SYNC
        9: '❌',  // SYSTEM_ERROR
        10: '👤', // USER_ACTION
        default: '📋'
    };
    return icons[type] || '📋';
}

function getEventClass(level) {
    switch(level) {
        case 2: return 'error';
        case 1: return 'warning';
        case 0: return level === 0 ? 'info' : 'success';
        default: return 'info';
    }
}

function formatEventTime(ms) {
    // 如果時間戳是大數字（> 10^12），當作 epoch 毫秒
    const now = Date.now();
    let date;
    
    if (ms > 1000000000000) {  // 超過 2001 年 = epoch 毫秒
        date = new Date(ms);
    } else if (ms > 10000000000) {  // 超過 1970 年 = epoch 秒
        date = new Date(ms * 1000);
    } else {
        // 這是運行時間（millis），顯示相對時間
        return `${(ms / 1000).toFixed(0)}s`;
    }
    
    return date.toLocaleTimeString('zh-TW', { hour12: false });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function clearEvents() {
    if (!confirm('確定要清除所有事件記錄嗎？')) return;
    
    try {
        await fetch(`${API_BASE}/events?clear=1`);
        refreshEvents();
        showToast('事件記錄已清除', 'success');
    } catch (error) {
        showToast('清除失敗', 'error');
    }
}

// ========== Toast 通知 ==========
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    container.appendChild(toast);
    
    // 自動刪除
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}
