@echo off
REM Daily agent runner - called by Windows Task Scheduler
REM Sets a fixed working directory so relative paths stay put.

cd /d "%~dp0"

REM Optional: point to a specific Python. Leave as-is to use PATH python.
set PYTHON=python

echo [%date% %time%] Starting daily agent run from %cd% >> daily_runner.log
%PYTHON% run_daily.py >> daily_runner.log 2>&1
echo [%date% %time%] Finished with exit code %ERRORLEVEL% >> daily_runner.log
exit /b %ERRORLEVEL%