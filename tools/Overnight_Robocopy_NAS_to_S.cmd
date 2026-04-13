@echo off
setlocal EnableExtensions

set "LOGDIR=C:\Starlight Manor Command\logs\robocopy"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%I"

set "OPTS=/E /COPY:DAT /DCOPY:T /R:2 /W:5 /MT:16 /ETA /TEE /FFT /XC /XN /XO"

set "PROG=%LOGDIR%\_batch_progress_%TS%.txt"
echo %date% %time% - START BATCH>"%PROG%"
echo Script: %~f0>>"%PROG%"
echo.>>"%PROG%"

echo %date% %time% - START MUSIC>>"%PROG%"
robocopy "\\SM-NAS-01\Media\Music" "S:\Media\Music" %OPTS% /LOG:"%LOGDIR%\Robocopy_Music_NAS_to_S_%TS%.log"
echo %date% %time% - END MUSIC (RC=%ERRORLEVEL%)>>"%PROG%"

echo %date% %time% - START PHOTOS>>"%PROG%"
robocopy "\\SM-NAS-01\Media\Photos" "S:\Media\Photos" %OPTS% /LOG:"%LOGDIR%\Robocopy_Photos_NAS_to_S_%TS%.log"
echo %date% %time% - END PHOTOS (RC=%ERRORLEVEL%)>>"%PROG%"

echo %date% %time% - START HOME MEDIA>>"%PROG%"
robocopy "\\SM-NAS-01\Media\Home Media" "S:\Media\Home Media" %OPTS% /LOG:"%LOGDIR%\Robocopy_HomeMedia_NAS_to_S_%TS%.log"
echo %date% %time% - END HOME MEDIA (RC=%ERRORLEVEL%)>>"%PROG%"

echo.>>"%PROG%"
echo %date% %time% - END BATCH>>"%PROG%"

echo All jobs complete.
exit /b 0
