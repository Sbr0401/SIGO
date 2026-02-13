@echo off
REM Scrcpy Auto-Setup Script for SIGO
REM Automatically downloads, configures, and launches scrcpy for phone screen capture

setlocal enabledelayedexpansion

echo ========================================
echo SCRCPY AUTO-SETUP FOR SIGO
echo ========================================
echo.

REM ========================================
REM Configuration
REM ========================================
set "SCRCPY_VERSION=2.7"
set "SCRCPY_URL=https://github.com/Genymobile/scrcpy/releases/download/v%SCRCPY_VERSION%/scrcpy-win64-v%SCRCPY_VERSION%.zip"
set "SCRCPY_DIR=%~dp0scrcpy"
set "SCRCPY_EXE=%SCRCPY_DIR%\scrcpy.exe"
set "ADB_EXE=%SCRCPY_DIR%\adb.exe"

REM Optimal scrcpy settings for SIGO
set "SCRCPY_MAX_SIZE=1280"
set "SCRCPY_BIT_RATE=8M"
set "SCRCPY_MAX_FPS=30"

REM ========================================
REM Check if scrcpy is already installed
REM ========================================
if exist "%SCRCPY_EXE%" (
    echo [OK] scrcpy found at: %SCRCPY_DIR%
    goto :check_phone
)

echo [INFO] scrcpy not found. Starting download...
echo.

REM ========================================
REM Download scrcpy
REM ========================================
echo [DOWNLOAD] Downloading scrcpy v%SCRCPY_VERSION%...
echo [INFO] This is a one-time download (~15MB)
echo.

REM Create temporary directory
set "TEMP_ZIP=%TEMP%\scrcpy-temp.zip"

REM Download using PowerShell (built-in to Windows)
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%SCRCPY_URL%' -OutFile '%TEMP_ZIP%'}"

if errorlevel 1 (
    echo [ERROR] Failed to download scrcpy.
    echo [ERROR] Check your internet connection or download manually from:
    echo [ERROR] https://github.com/Genymobile/scrcpy/releases
    pause
    exit /b 1
)

echo [OK] Download complete.
echo.

REM ========================================
REM Extract scrcpy
REM ========================================
echo [EXTRACT] Extracting scrcpy...

REM Extract using PowerShell
powershell -Command "& {Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%~dp0' -Force}"

if errorlevel 1 (
    echo [ERROR] Failed to extract scrcpy.
    pause
    exit /b 1
)

REM Rename extracted folder to "scrcpy"
for /d %%i in ("%~dp0scrcpy-win64-v*") do (
    if exist "%%i" (
        move "%%i" "%SCRCPY_DIR%" >nul 2>&1
    )
)

REM Clean up
del "%TEMP_ZIP%" >nul 2>&1

echo [OK] scrcpy installed successfully.
echo.

REM ========================================
REM Check phone connection
REM ========================================
:check_phone

echo [CHECK] Looking for connected phone...

REM Get devices and check for connected device
set "DEVICE_ID="
for /f "skip=1 tokens=1,2" %%a in ('"%ADB_EXE%" devices 2^>nul') do (
    if "%%b"=="device" (
        set "DEVICE_ID=%%a"
    )
)

if not defined DEVICE_ID (
    echo [WARNING] No phone detected!
    echo.
    echo Please ensure:
    echo   1. Phone is connected via USB
    echo   2. USB debugging is enabled on phone
    echo      - Go to Settings ^> About Phone
    echo      - Tap "Build Number" 7 times to enable Developer Options
    echo      - Go to Settings ^> Developer Options
    echo      - Enable "USB Debugging"
    echo   3. Allow USB debugging when prompted on phone
    echo   4. Accept computer's RSA fingerprint (important!)
    echo.
    echo Press any key to retry detection...
    pause >nul
    goto :check_phone
)

echo [OK] Phone detected: !DEVICE_ID!
echo.

REM Get phone model
for /f "delims=" %%i in ('"%ADB_EXE%" shell getprop ro.product.model 2^>nul') do set "PHONE_MODEL=%%i"
echo [INFO] Model: !PHONE_MODEL!
echo.

REM ========================================
REM Launch scrcpy
REM ========================================
echo [LAUNCH] Starting scrcpy with SIGO-optimized settings...
echo.
echo Settings:
echo   - Max resolution: %SCRCPY_MAX_SIZE%p
echo   - Bitrate: %SCRCPY_BIT_RATE%
echo   - Max FPS: %SCRCPY_MAX_FPS%
echo   - Stay awake: enabled
echo   - Turn screen off: disabled (keep visible)
echo.
echo [INFO] scrcpy window will open. Keep it running for SIGO to capture.
echo [INFO] Press Ctrl+C in this terminal to stop scrcpy.
echo.
echo ========================================
echo SCRCPY RUNNING
echo ========================================
echo.

REM Launch scrcpy with optimal settings
"%SCRCPY_EXE%" ^
    --max-size=%SCRCPY_MAX_SIZE% ^
    --bit-rate=%SCRCPY_BIT_RATE% ^
    --max-fps=%SCRCPY_MAX_FPS% ^
    --stay-awake ^
    --turn-screen-off=false ^
    --no-audio ^
    --window-title="SIGO Phone Screen"

if errorlevel 1 (
    echo.
    echo [ERROR] scrcpy failed to start.
    echo.
    echo Common issues:
    echo   1. Phone disconnected - check USB cable
    echo   2. USB debugging disabled - re-enable on phone
    echo   3. Another scrcpy instance running - close it first
    echo   4. ADB authorization revoked - re-accept on phone
    echo.
    pause
    exit /b 1
)

echo.
echo [EXIT] scrcpy closed.
echo.
pause
exit /b 0
