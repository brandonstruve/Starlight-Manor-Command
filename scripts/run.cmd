@echo off
TITLE Deploy Starlight Manor Task

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~dpnx0\"' -Verb RunAs"
    exit /b
)

echo ===================================================
echo Deploying Task Scheduler Job for Starlight Manor
echo ===================================================
echo.

set TASK_NAME=Starlight Manor\HA Event Sync
set TASK_ACTION=C:\Starlight Manor Command\sync_ha_events.cmd
set RUN_TIME=03:00

:: Create the scheduled task to run daily at 3:00 AM with highest privileges
schtasks /create /tn "%TASK_NAME%" /tr "\"%TASK_ACTION%\"" /sc daily /st %RUN_TIME% /rl HIGHEST /f

echo.
echo [SUCCESS] Task "%TASK_NAME%" scheduled to run daily at %RUN_TIME%.
echo.
echo IMPORTANT SECURITY NOTE: 
echo Because this script accesses a network share (Home Assistant), it runs under your user account. 
echo By default, schtasks creates this to run "Only when user is logged on." 
echo.
echo If your server fully logs you out, you will need to open Task Scheduler manually once,
echo right-click the task, check "Run whether user is logged on or not", and type your password. 
echo (We leave this out of the script so your Windows password isn't sitting in plain text in a batch file).
echo.
pause