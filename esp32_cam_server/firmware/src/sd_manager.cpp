#include "sd_manager.h"
#include "config/config.h"
#include <SPI.h>

#define SD_PIN_CS 4       // 需依開發板調整
#define SD_PIN_SCK 18
#define SD_PIN_MOSI 23
#define SD_PIN_MISO 19

SDManager::SDManager()
    : _mounted(false)
    , _image_dir("/sdcard/images")
    , _log_file("/sdcard/log.txt")
    , _config_file("/sdcard/config.txt") {
    memset(&_status, 0, sizeof(_status));
}

SDManager::~SDManager() {
    end();
}

bool SDManager::begin() {
    Serial.println("[SD] Initializing SD card...");
    
    // 初始化 SPI 匯流排
    SPI.begin(SD_PIN_SCK, SD_PIN_MISO, SD_PIN_MOSI, SD_PIN_CS);
    
    if (!SD_MMC.begin("/sdcard", true, SD_PIN_CS, 4000000)) {
        Serial.println("[SD] Card Mount Failed");
        return false;
    }
    
    _mounted = true;
    updateStatus();
    
    // 創建所需目錄
    if (!ensureDirectories()) {
        Serial.println("[SD] Directory creation failed");
    }
    
    Serial.printf("[SD] Mounted successfully: %llu bytes free\n", getFreeSpace());
    
    // 記錄啟動
    appendLog("System started");
    
    return true;
}

void SDManager::end() {
    if (_mounted) {
        SD_MMC.end();
        _mounted = false;
        Serial.println("[SD] Card unmounted");
    }
}

bool SDManager::saveImage(camera_fb_t* fb, uint8_t trigger_type, char* out_filename) {
    if (!_mounted || !fb || !fb->buf) {
        Serial.println("[SD] Save failed: not mounted or invalid frame");
        return false;
    }
    
    String filename = generateFilename(trigger_type);
    String full_path = _image_dir + "/" + filename;
    
    // 寫入檔案
    File file = SD_MMC.open(full_path, FILE_WRITE);
    if (!file) {
        Serial.printf("[SD] Failed to open file: %s\n", full_path.c_str());
        return false;
    }
    
    size_t written = file.write(fb->buf, fb->len);
    file.close();
    
    if (written != fb->len) {
        Serial.printf("[SD] Write incomplete: %d/%d\n", written, fb->len);
        return false;
    }
    
    Serial.printf("[SD] Image saved: %s (%d bytes)\n", filename.c_str(), written);
    
    if (out_filename) {
        strncpy(out_filename, filename.c_str(), 63);
    }
    
    // 記錄事件
    char log[128];
    snprintf(log, sizeof(log), "Image saved: %s, trigger=%d, size=%d",
             filename.c_str(), trigger_type, written);
    appendLog(log);
    
    return true;
}

bool SDManager::saveImageBuffer(const uint8_t* data, size_t length, const char* filename) {
    if (!_mounted || !data || length == 0) {
        return false;
    }
    
    String full_path = _image_dir + "/" + filename;
    
    File file = SD_MMC.open(full_path, FILE_WRITE);
    if (!file) {
        return false;
    }
    
    size_t written = file.write(data, length);
    file.close();
    
    return written == length;
}

bool SDManager::listImages(image_info_t* images, uint8_t max_count, uint8_t* return_count) {
    if (!_mounted || !images || !return_count) {
        return false;
    }
    
    File dir = SD_MMC.open(_image_dir);
    if (!dir) {
        return false;
    }
    
    uint8_t count = 0;
    File file = dir.openNextFile();
    
    while (file && count < max_count) {
        if (!file.isDirectory()) {
            String name = file.name();
            if (name.endsWith(".jpg")) {
                strncpy(images[count].filename, name.c_str(), 63);
                images[count].size = file.size();
                images[count].timestamp = 0;  // 可從檔名解析
                count++;
            }
        }
        file = dir.openNextFile();
    }
    
    file.close();
    dir.close();
    
    *return_count = count;
    Serial.printf("[SD] Listed %d images\n", count);
    return true;
}

bool SDManager::deleteImage(const char* filename) {
    if (!_mounted) return false;
    
    String full_path = _image_dir + "/" + filename;
    bool result = SD_MMC.remove(full_path);
    
    if (result) {
        Serial.printf("[SD] Deleted: %s\n", filename);
        String msg = "Image deleted: " + String(filename);
        appendLog(msg.c_str());
    }
    
    return result;
}

bool SDManager::clearAllImages() {
    if (!_mounted) return false;
    
    File dir = SD_MMC.open(_image_dir);
    if (!dir) return false;
    
    uint32_t deleted = 0;
    File file = dir.openNextFile();
    
    while (file) {
        if (!file.isDirectory()) {
            String path = file.path();
            file.close();
            if (SD_MMC.remove(path)) {
                deleted++;
            }
        } else {
            file.close();
        }
        file = dir.openNextFile();
    }
    dir.close();
    
    Serial.printf("[SD] Cleared %ld images\n", deleted);
        String msg = "Cleared " + String(deleted) + " images";
        appendLog(msg.c_str());
    
    return true;
}

bool SDManager::deleteOldFiles(uint32_t older_than_days) {
    if (!_mounted) return false;
    
    File dir = SD_MMC.open(_image_dir);
    if (!dir) return false;
    
    uint32_t deleted = 0;
    unsigned long current_time = millis() / 1000;
    
    File file = dir.openNextFile();
    while (file) {
        if (!file.isDirectory()) {
            // 檢查檔案時間
            time_t file_time = file.getLastWrite();
            if (file_time > 0) {
                if ((millis() / 1000) > older_than_days * 86400UL) {
                    String path = file.path();
                    file.close();
                    if (SD_MMC.remove(path)) {
                        deleted++;
                    }
                }
            }
        }
        file = dir.openNextFile();
    }
    dir.close();
    
    if (deleted > 0) {
        Serial.printf("[SD] Deleted %ld old files\n", deleted);
        String msg = "Deleted " + String(deleted) + " old files";
        appendLog(msg.c_str());
    }
    
    return true;
}

size_t SDManager::getTotalFileCount() {
    if (!_mounted) return 0;
    
    File dir = SD_MMC.open(_image_dir);
    if (!dir) return 0;
    
    size_t count = 0;
    File file = dir.openNextFile();
    while (file) {
        if (!file.isDirectory()) {
            count++;
        }
        file = dir.openNextFile();
    }
    file.close();
    dir.close();
    
    return count;
}

bool SDManager::appendLog(const char* log_entry) {
    if (!_mounted) return false;
    
    File file = SD_MMC.open(_log_file, FILE_APPEND);
    if (!file) {
        return false;
    }
    
    String entry = "[" + String(millis()) + "] " + log_entry + "\n";
    size_t written = file.print(entry);
    file.close();
    
    return written > 0;
}

bool SDManager::saveConfig(const char* key, const char* value) {
    if (!_mounted) return false;
    
    // 讀取現有配置
    String content = "";
    if (SD_MMC.exists(_config_file)) {
        File file = SD_MMC.open(_config_file, FILE_READ);
        content = file.readString();
        file.close();
    }
    
    // 更新或添加配置項
    bool found = false;
    String new_content = "";
    int pos = 0;
    
    while (pos < content.length()) {
        int line_end = content.indexOf('\n', pos);
        if (line_end < 0) line_end = content.length();
        
        String line = content.substring(pos, line_end);
        pos = line_end + 1;
        
        if (line.startsWith(String(key) + "=")) {
            new_content += String(key) + "=" + value + "\n";
            found = true;
        } else {
            new_content += line + "\n";
        }
    }
    
    if (!found) {
        new_content += String(key) + "=" + value + "\n";
    }
    
    // 寫回檔案
    File file = SD_MMC.open(_config_file, FILE_WRITE);
    if (!file) {
        return false;
    }
    
    file.print(new_content);
    file.close();
    
    return true;
}

bool SDManager::loadConfig(const char* key, char* value, size_t max_len) {
    if (!_mounted || !value) return false;
    
    if (!SD_MMC.exists(_config_file)) {
        return false;
    }
    
    File file = SD_MMC.open(_config_file, FILE_READ);
    if (!file) {
        return false;
    }
    
    String search_key = String(key) + "=";
    bool found = false;
    
    while (file.available()) {
        String line = file.readStringUntil('\n');
        line.trim();
        
        if (line.startsWith(search_key)) {
            String val = line.substring(search_key.length());
            strncpy(value, val.c_str(), max_len - 1);
            value[max_len - 1] = '\0';
            found = true;
            break;
        }
    }
    
    file.close();
    return found;
}

sd_status_t SDManager::getStatus() const {
    return _status;
}

bool SDManager::isMounted() const {
    return _mounted;
}

uint64_t SDManager::getFreeSpace() const {
    if (!_mounted) return 0;
    return SD_MMC.cardSize() - SD_MMC.usedBytes();
}

void SDManager::listRoot() {
    if (!_mounted) return;
    
    Serial.println("[SD] Root directory:");
    File root = SD_MMC.open("/");
    
    File file = root.openNextFile();
    while (file) {
        if (file.isDirectory()) {
            Serial.print("  DIR /");
            Serial.println(file.name());
        } else {
            Serial.print("  FILE /");
            Serial.print(file.name());
            Serial.printf(" (%d bytes)\n", file.size());
        }
        file = root.openNextFile();
    }
    file.close();
    root.close();
}

bool SDManager::ensureDirectories() {
    bool success = true;
    
    if (!SD_MMC.exists("/images")) {
        success &= SD_MMC.mkdir("/images");
        Serial.println("[SD] Created /images directory");
    }
    
    _image_dir = "/images";
    
    // 更新日誌目錄
    _log_file = "/log.txt";
    _config_file = "/config.txt";
    
    return success;
}

void SDManager::updateStatus() {
    if (!_mounted) return;
    
    _status.mounted = true;
    _status.total_bytes = SD_MMC.cardSize();
    _status.used_bytes = SD_MMC.usedBytes();
    _status.file_count = getTotalFileCount();
    
    _status.card_type = SD_MMC.cardType();
}

String SDManager::generateFilename(uint8_t trigger_type) {
    char filename[64];
    
    // 時間戳記檔名
    time_t now;
    struct tm timeinfo;
    if (!getLocalTime(&timeinfo)) {
        // 如果沒有 NTP 時間，使用 millis
        snprintf(filename, sizeof(filename), "IMG_%lu_%d.jpg", millis(), trigger_type);
        return String(filename);
    }
    
    char type_char;
    switch (trigger_type) {
        case 0: type_char = 'P'; break;  // PIR
        case 1: type_char = 'M'; break;  // Motion
        case 2: type_char = 'T'; break;  // Timer
        case 3: type_char = 'H'; break;  // Manual
        default: type_char = 'X'; break;
    }
    
    snprintf(filename, sizeof(filename), "%04d%02d%02d_%02d%02d%02d_%c.jpg",
             timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
             timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec,
             type_char);
    
    return String(filename);
}

bool SDManager::isValidImageData(const uint8_t* data, size_t length) {
    if (!data || length < 10) return false;
    
    // 檢查 JPEG 檔頭
    return (data[0] == 0xFF && data[1] == 0xD8) ||  // SOI
           (data[0] == 0x00 && data[1] == 0x00);    // 原始格式
}
