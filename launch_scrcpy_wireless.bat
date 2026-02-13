@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM SIGO - Wireless Scrcpy for DJI Spark
REM ============================================================
REM 1. Phone plugged in via USB
REM 2. adb tcpip 5555
REM 3. Get IP from phone via: adb shell ip route
REM 4. adb connect <IP>:5555
REM 5. Unplug phone, plug into DJI Controller
REM 6. scrcpy streams wirelessly
REM ============================================================

color 0A
title SIGO - Wireless Scrcpy

set "SCRCPY_VERSION=2.7"
set "SCRCPY_URL=https://github.com/Genymobile/scrcpy/releases/download/v%SCRCPY_VERSION%/scrcpy-win64-v%SCRCPY_VERSION%.zip"
set "SCRCPY_DIR=%~dp0scrcpy"
set "SCRCPY_EXE=%SCRCPY_DIR%\scrcpy.exe"
set "ADB_EXE=%SCRCPY_DIR%\adb.exe"
set "ADB_PORT=5555"

echo.
echo ============================================================
echo   SIGO - Wireless Scrcpy (DJI Spark)
echo ============================================================
echo.

REM --- Install scrcpy if needed --------------------------------
if exist "%SCRCPY_EXE%" (
    echo [OK] scrcpy found.
) else (
    echo [INFO] scrcpy not found. Downloading v%SCRCPY_VERSION%...
    set "TEMP_ZIP=%TEMP%\scrcpy-temp.zip"
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%SCRCPY_URL%' -OutFile '!TEMP_ZIP!'}"
    if errorlevel 1 (
        echo [ERROR] Download failed. Get it manually: %SCRCPY_URL%
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

REM --- Check if already connected wirelessly -------------------
set "DEVTMP=%TEMP%\sigo_adb_devices.txt"
"%ADB_EXE%" devices > "%DEVTMP%" 2>nul

set "WIRELESS_DEVICE="
set "USB_DEVICE="
for /f "skip=1 tokens=1,2" %%a in ('type "%DEVTMP%"') do (
    if "%%b"=="device" (
        echo %%a | findstr /C:":" >nul
        if !errorlevel! EQU 0 (
            set "WIRELESS_DEVICE=%%a"
        ) else (
            set "USB_DEVICE=%%a"
        )
    )
)
del "%DEVTMP%" >nul 2>&1

if defined WIRELESS_DEVICE (
    echo [OK] Already connected wirelessly: !WIRELESS_DEVICE!
    goto :launch_scrcpy
)

if defined USB_DEVICE goto :phone_found

REM --- Wait for USB phone --------------------------------------
echo  Plug your phone into this PC via USB cable.
echo  (Just temporarily to get the IP and enable wireless ADB)
echo.

:wait_usb
set "USB_DEVICE="
"%ADB_EXE%" devices > "%DEVTMP%" 2>nul
for /f "skip=1 tokens=1,2" %%a in ('type "%DEVTMP%"') do (
    if "%%b"=="device" (
        echo %%a | findstr /C:":" >nul
        if !errorlevel! NEQ 0 set "USB_DEVICE=%%a"
    )
)
del "%DEVTMP%" >nul 2>&1

if not defined USB_DEVICE (
    echo    Waiting for phone... (make sure USB Debugging is on)
    timeout /t 3 >nul
    goto :wait_usb
)

:phone_found
for /f "delims=" %%i in ('"%ADB_EXE%" -s !USB_DEVICE! shell getprop ro.product.model 2^>nul') do set "PHONE_MODEL=%%i"
echo [OK] Phone: !PHONE_MODEL! (!USB_DEVICE!)
echo.

REM --- Enable wireless ADB ------------------------------------
echo [INFO] adb tcpip %ADB_PORT%
"%ADB_EXE%" -s !USB_DEVICE! tcpip %ADB_PORT%
if !errorlevel! NEQ 0 (
    echo [ERROR] Failed. Make sure USB debugging is authorized.
    pause
    exit /b 1
)
timeout /t 2 >nul
echo [OK] Wireless ADB enabled.
echo.

REM --- Get phone IP from the phone itself ----------------------
echo [INFO] adb shell ip route
set "PHONE_IP="
for /f "tokens=*" %%r in ('"%ADB_EXE%" -s !USB_DEVICE! shell ip route 2^>nul') do (
    if not defined PHONE_IP (
        for /f "tokens=9" %%a in ("%%r") do (
            set "PHONE_IP=%%a"
        )
    )
)

if not defined PHONE_IP (
    echo [WARN] Could not get IP from phone.
    set /p "PHONE_IP=Enter phone IP manually: "
)

echo [OK] Phone IP: !PHONE_IP!
echo.

REM --- Connect wirelessly --------------------------------------
echo [INFO] adb connect !PHONE_IP!:%ADB_PORT%
"%ADB_EXE%" connect !PHONE_IP!:%ADB_PORT%
timeout /t 2 >nul

REM Verify connection
"%ADB_EXE%" devices 2>nul | findstr /C:"!PHONE_IP!:%ADB_PORT!" | findstr /C:"device" >nul
if errorlevel 1 (
    echo [WARN] Not connected yet, retrying...
    timeout /t 3 >nul
    "%ADB_EXE%" connect !PHONE_IP!:%ADB_PORT%
    timeout /t 2 >nul
)

set "WIRELESS_DEVICE=!PHONE_IP!:%ADB_PORT%"
echo.
echo [OK] Connected: !WIRELESS_DEVICE!
echo.
echo  -----------------------------------------------------------
echo   Now unplug the phone from USB and plug into DJI Controller
echo   Then connect this PC's WiFi to the phone's hotspot.
echo.
echo   Press any key when ready...
echo  -----------------------------------------------------------
pause >nul
echo.

REM --- Launch scrcpy -------------------------------------------
:launch_scrcpy
echo  -----------------------------------------------------------
echo   SCRCPY RUNNING  (Ctrl+C to stop)
echo   Device: !WIRELESS_DEVICE!
echo  -----------------------------------------------------------
echo.

echo !WIRELESS_DEVICE!> "%~dp0.scrcpy_device"

"%SCRCPY_EXE%" --serial=!WIRELESS_DEVICE! --window-title "scrcpy" --video-bit-rate 12M --max-size 2340 --max-fps 30 --no-control --no-audio

if errorlevel 1 (
    echo.
    echo [ERROR] scrcpy exited with an error.
    echo    Re-run this script to reconnect.
    echo.
    pause
    exit /b 1
)

echo.
echo [DONE] scrcpy closed.
del "%~dp0.scrcpy_device" >nul 2>&1
pause
exit /b 0
