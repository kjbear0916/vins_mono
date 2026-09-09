@echo off
REM ============================================
REM 鼠患智能監控系統 - 燒錄腳本
REM ============================================
chcp 65001 >nul
title Rat Monitor Flash Utility

echo.
echo  ============================================
echo   鼠患智能監控系統 - 程式燒錄工具
echo  ============================================
echo.
echo  可用操作：
echo    [1] 燒錄韌體 (PlatformIO)
echo    [2] 燒錄韌體 (esptool)
echo    [3] 清除 Flash
echo    [4] 監控 Serial 輸出
echo    [5] 編譯
echo    [0] 退出
echo.
set /p choice="請選擇操作 (0-5): "

if "%choice%"=="1" (
    echo.
    echo 開始燒錄 (PlatformIO)...
    pio run -t upload
    goto done
)

if "%choice%"=="2" (
    echo.
    set /p port="請輸入串口 (如 COM3): "
    echo 開始燒錄...
    esptool.py --chip esp32s3 --port %port% write_flash -z 0x0 build/esp32s3/firmware.bin
    goto done
)

if "%choice%"=="3" (
    echo.
    echo 清除 Flash...
    set /p port="請輸入串口 (如 COM3): "
    esptool.py --chip esp32s3 --port %port% erase_flash
    goto done
)

if "%choice%"=="4" (
    echo.
    echo 開始監控 Serial 輸出...
    pio device monitor
    goto done
)

if "%choice%"=="5" (
    echo.
    echo 開始編譯...
    pio run
    goto done
)

if "%choice%"=="0" (
    exit /b 0
)

:done
echo.
echo 操作完成！
pause
