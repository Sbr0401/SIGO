@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================================
:: SIGO — Wireless Scrcpy Setup for DJI Spark + Android
:: ============================================================
:: Workflow:
::   1. Plug phone into PC via USB (temporarily)
::   2. This script enables wireless ADB
::   3. Unplug phone and connect it to the DJI Controller
::   4. scrcpy streams the DJI GO 4 screen wirelessly to the PC
:: ============================================================

color 0A
title SIGO — Wireless Scrcpy Setup

set "SCRCPY_VERSION=2.7"
set "SCRCPY_URL=https://github.com/Genymobile/scrcpy/releases/download/v%SCRCPY_VERSION%/scrcpy-win64-v%SCRCPY_VERSION%.zip"
set "SCRCPY_DIR=%~dp0scrcpy"
set "SCRCPY_EXE=%SCRCPY_DIR%\scrcpy.exe"
set "ADB_EXE=%SCRCPY_DIR%\adb.exe"

:: Optimal scrcpy settings for DJI GO 4 capture
set "SCRCPY_MAX_SIZE=1280"
set "SCRCPY_BIT_RATE=8M"
set "SCRCPY_MAX_FPS=30"
set "ADB_PORT=5555"

echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║     SIGO — Wireless Scrcpy (DJI Spark Setup)            ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.

:: ─── Step 0: Check/install scrcpy ────────────────────────────
if exist "%SCRCPY_EXE%" (
    echo [OK] scrcpy found at: %SCRCPY_DIR%
) else (
    echo [INFO] scrcpy not found. Downloading v%SCRCPY_VERSION%...
    
    set "TEMP_ZIP=%TEMP%\scrcpy-temp.zip"
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%SCRCPY_URL%' -OutFile '!TEMP_ZIP!'}"
    
    if errorlevel 1 (
        echo [ERROR] Download failed. Check internet or download manually:
        echo         %SCRCPY_URL%
        pause
        exit /b 1
    )
    
    echo [OK] Downloaded. Extracting...
    powershell -Command "& {Expand-Archive -Path '!TEMP_ZIP!' -DestinationPath '%~dp0' -Force}"
    
    for /d %%i in ("%~dp0scrcpy-win64-v*") do (
        if exist "%%i" move "%%i" "%SCRCPY_DIR%" >nul 2>&1
    )
    del "!TEMP_ZIP!" >nul 2>&1
    
    if not exist "%SCRCPY_EXE%" (
        echo [ERROR] Installation failed.
        pause
        exit /b 1
    )
    echo [OK] scrcpy installed.
)
echo.

:: ─── Step 1: Check if already connected wirelessly ───────────
echo [CHECK] Checking for existing wireless connection...

:: Kill any stale ADB server first
"%ADB_EXE%" start-server >nul 2>&1

:: Check for any wireless device already connected
set "WIRELESS_DEVICE="
for /f "tokens=1,2" %%a in ('"%ADB_EXE%" devices 2^>nul') do (
    echo %%a | findstr /C:":" >nul 2>&1
    if not errorlevel 1 (
        if "%%b"=="device" (
            set "WIRELESS_DEVICE=%%a"
        )
    )
)

if defined WIRELESS_DEVICE (
    echo [OK] Already connected wirelessly to: !WIRELESS_DEVICE!
    echo.
    goto :launch_scrcpy_wireless
)

:: ─── Step 2: Look for USB-connected phone ────────────────────
echo.
echo ════════════════════════════════════════════════════════════
echo  STEP 1: Connect your Android phone to the PC via USB
echo          (temporarily — to set up wireless ADB)
echo ════════════════════════════════════════════════════════════
echo.

:wait_usb
set "USB_DEVICE="
for /f "skip=1 tokens=1,2" %%a in ('"%ADB_EXE%" devices 2^>nul') do (
    if "%%b"=="device" (
        :: Check it's not already a wireless device
        echo %%a | findstr /C:":" >nul 2>&1
        if errorlevel 1 (
            set "USB_DEVICE=%%a"
        )
    )
)

if not defined USB_DEVICE (
    echo [WAITING] No phone detected via USB. Plug in your phone...
    echo           Make sure USB Debugging is enabled.
    timeout /t 3 >nul
    goto :wait_usb
)

echo [OK] Phone detected via USB: !USB_DEVICE!

:: Get phone model
for /f "delims=" %%i in ('"%ADB_EXE%" -s !USB_DEVICE! shell getprop ro.product.model 2^>nul') do set "PHONE_MODEL=%%i"
echo [INFO] Model: !PHONE_MODEL!
echo.

:: ─── Step 3: Get phone's WiFi IP ────────────────────────────
echo [INFO] Getting phone's WiFi IP address...

set "PHONE_IP="
for /f "tokens=*" %%i in ('"%ADB_EXE%" -s !USB_DEVICE! shell ip route show dev wlan0 2^>nul ^| findstr /C:"src"') do (
    for %%j in (%%i) do (
        echo %%j | findstr /R "^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$" >nul 2>&1
        if not errorlevel 1 (
            if not defined PHONE_IP set "PHONE_IP=%%j"
        )
    )
)

:: Fallback: try wlan0 ifconfig
if not defined PHONE_IP (
    for /f "tokens=2 delims=:" %%i in ('"%ADB_EXE%" -s !USB_DEVICE! shell ifconfig wlan0 2^>nul ^| findstr /C:"inet addr"') do (
        for /f "tokens=1" %%j in ("%%i") do set "PHONE_IP=%%j"
    )
)

:: Fallback: ip addr
if not defined PHONE_IP (
    for /f "tokens=2 delims=/" %%i in ('"%ADB_EXE%" -s !USB_DEVICE! shell "ip addr show wlan0 | grep inet " 2^>nul') do (
        for /f "tokens=1" %%j in ("%%i") do (
            if not defined PHONE_IP set "PHONE_IP=%%j"
        )
    )
)

if not defined PHONE_IP (
    echo [ERROR] Could not detect phone's WiFi IP address.
    echo         Make sure the phone is connected to the same WiFi as the PC.
    echo.
    echo         You can enter the phone's IP manually.
    set /p "PHONE_IP=Phone IP address: "
)

if not defined PHONE_IP (
    echo [ERROR] No IP provided. Aborting.
    pause
    exit /b 1
)

echo [OK] Phone WiFi IP: !PHONE_IP!
echo.

:: ─── Step 4: Enable TCP/IP ADB mode ─────────────────────────
echo [INFO] Enabling wireless ADB on port %ADB_PORT%...
"%ADB_EXE%" -s !USB_DEVICE! tcpip %ADB_PORT%

if errorlevel 1 (
    echo [ERROR] Failed to enable wireless ADB.
    echo         Make sure USB debugging is authorized.
    pause
    exit /b 1
)

:: Give the phone a moment to switch to TCP mode
timeout /t 2 >nul

echo [OK] Wireless ADB enabled.
echo.

:: ─── Step 5: Prompt user to disconnect and connect to DJI ───
echo ════════════════════════════════════════════════════════════
echo  STEP 2: Disconnect the phone from the PC USB
echo          and plug it into the DJI Spark Controller.
echo.
echo          Then press any key to continue.
echo ════════════════════════════════════════════════════════════
echo.
pause >nul

:: ─── Step 6: Connect wirelessly ──────────────────────────────
echo [INFO] Connecting wirelessly to !PHONE_IP!:%ADB_PORT%...

:: Retry a few times in case the phone needs a moment
set "CONNECTED=0"
for /L %%i in (1,1,5) do (
    if !CONNECTED! EQU 0 (
        "%ADB_EXE%" connect !PHONE_IP!:%ADB_PORT% 2>nul | findstr /C:"connected" >nul
        if not errorlevel 1 (
            set "CONNECTED=1"
        ) else (
            echo [RETRY %%i/5] Waiting for wireless connection...
            timeout /t 2 >nul
        )
    )
)

if !CONNECTED! EQU 0 (
    echo.
    echo [ERROR] Could not connect wirelessly to !PHONE_IP!:%ADB_PORT%
    echo.
    echo Troubleshooting:
    echo   - Ensure the phone and PC are on the same WiFi network
    echo   - Check if a firewall is blocking port %ADB_PORT%
    echo   - Try: %ADB_EXE% connect !PHONE_IP!:%ADB_PORT%
    echo.
    pause
    exit /b 1
)

echo [OK] Connected wirelessly to !PHONE_IP!:%ADB_PORT%
echo.
set "WIRELESS_DEVICE=!PHONE_IP!:%ADB_PORT%"

:: ─── Step 7: Launch scrcpy wirelessly ────────────────────────
:launch_scrcpy_wireless
echo ════════════════════════════════════════════════════════════
echo  LAUNCHING SCRCPY (Wireless)
echo ════════════════════════════════════════════════════════════
echo.
echo  Settings:
echo    Device:     !WIRELESS_DEVICE!
echo    Resolution: %SCRCPY_MAX_SIZE%p
echo    Bitrate:    %SCRCPY_BIT_RATE%
echo    FPS:        %SCRCPY_MAX_FPS%
echo.
echo  The scrcpy window will show your phone screen.
echo  Open DJI GO 4 on the phone, then start SIGO with
echo  source "2 - Scrcpy (Android)" to begin.
echo.
echo  Press Ctrl+C here to stop scrcpy when finished.
echo ════════════════════════════════════════════════════════════
echo.

:: Save the wireless device IP for SIGO to use (optional reconnect)
echo !WIRELESS_DEVICE!> "%~dp0.scrcpy_device"

"%SCRCPY_EXE%" ^
    --serial=!WIRELESS_DEVICE! ^
    --max-size=%SCRCPY_MAX_SIZE% ^
    --video-bit-rate=%SCRCPY_BIT_RATE% ^
    --max-fps=%SCRCPY_MAX_FPS% ^
    --stay-awake ^
    --no-audio ^
    --power-off-on-close=false ^
    --window-title="scrcpy"

if errorlevel 1 (
    echo.
    echo [ERROR] scrcpy failed. Possible causes:
    echo   - Phone disconnected from WiFi
    echo   - Wireless ADB session expired (re-run this script)
    echo   - DJI GO 4 not running on the phone
    echo.
    pause
    exit /b 1
)

echo.
echo [EXIT] scrcpy closed.

:: Clean up device file
del "%~dp0.scrcpy_device" >nul 2>&1

pause
exit /b 0
