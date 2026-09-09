#ifndef SD_MANAGER_H
#define SD_MANAGER_H

#include <Arduino.h>
#include <FS.h>
#include <SD_MMC.h>
#include <esp_camera.h>

// 影像資訊結構
typedef struct {
    char filename[64];
    uint32_t timestamp;
    uint16_t width;
    uint16_t height;
    size_t size;
    uint8_t trigger_type;  // 0=PIR, 1=動態偵測, 2=定時, 3=手動
} image_info_t;

// SD 卡狀態
typedef struct {
    bool mounted;
    uint64_t total_bytes;
    uint64_t used_bytes;
    uint32_t file_count;
    uint8_t card_type;  // 0=None, 1=MMC, 2=SDSC, 3=SDHC/SDXC
} sd_status_t;

class SDManager {
public:
    SDManager();
    ~SDManager();

    // 初始化
    bool begin();
    void end();

    // 影像存儲
    bool saveImage(camera_fb_t* fb, uint8_t trigger_type, char* out_filename = NULL);
    bool saveImageBuffer(const uint8_t* data, size_t length, const char* filename);
    
    // 檔案管理
    bool listImages(image_info_t* images, uint8_t max_count, uint8_t* return_count);
    bool deleteImage(const char* filename);
    bool clearAllImages();
    bool deleteOldFiles(uint32_t older_than_days);
    size_t getTotalFileCount();

    // 資料記錄
    bool appendLog(const char* log_entry);
    bool saveConfig(const char* key, const char* value);
    bool loadConfig(const char* key, char* value, size_t max_len);

    // 狀態
    sd_status_t getStatus() const;
    bool isMounted() const;
    uint64_t getFreeSpace() const;

    // 格式化
    void listRoot();

private:
    bool _mounted;
    sd_status_t _status;
    
    String _image_dir;
    String _log_file;
    String _config_file;

    // 內部方法
    bool ensureDirectories();
    void updateStatus();
    String generateFilename(uint8_t trigger_type);
    bool isValidImageData(const uint8_t* data, size_t length);
};

#endif // SD_MANAGER_H
