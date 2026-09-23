@echo off
REM Register a Windows Task Scheduler task that runs run_daily.bat every day at 09:00.
REM Run with admin rights:  right-click -> Run as administrator
REM Custom time:  schtasks /run /tn "ClaudeDailyAgent"  to trigger manually.

set BATFILE=%~dp0run_daily.bat

schtasks /Create /TN "ClaudeDailyAgent" /TR "%BATFILE%" /SC DAILY /ST 09:00 /F

if %ERRORLEVEL%==0 (
    echo.
    echo Task "ClaudeDailyAgent" created. Runs daily at 09:00.
    echo Manual trigger: schtasks /run /tn "ClaudeDailyAgent"
    echo Delete:         schtasks /Delete /tn "ClaudeDailyAgent" /F
) else (
    echo Failed to create task. Make sure you ran as administrator.
)