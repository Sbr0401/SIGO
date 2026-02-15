@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================
:: SIGO - Script de Instalacion Automatica
:: ============================================

color 0A
title SIGO - Instalacion y Configuracion

set "SCRCPY_VERSION=2.7"
set "SCRCPY_URL=https://github.com/Genymobile/scrcpy/releases/download/v%SCRCPY_VERSION%/scrcpy-win64-v%SCRCPY_VERSION%.zip"
set "SCRCPY_DIR=%~dp0scrcpy"
set "SCRCPY_EXE=%SCRCPY_DIR%\scrcpy.exe"
set "ADB_EXE=%SCRCPY_DIR%\adb.exe"
set "ADB_PORT=5555"

:MENU
cls
echo.
echo  ==============================================================
echo             SIGO - Sistema de Instalacion Automatica
echo  ==============================================================
echo.
echo   [1] Instalacion Completa (Todo incluido)
echo   [2] Instalacion Basica (Sin reconocimiento facial)
echo   [3] Instalacion CPU (Sin GPU)
echo   [4] Solo Reconocimiento Facial
echo   [5] Solo Paquetes de Rendimiento
echo   [6] Verificar Instalacion
echo   [7] Crear/Activar Entorno Virtual
echo   [8] Configurar OpenAI API Key
echo   [9] Conectar Scrcpy Wireless (DJI Spark)
echo   [S] Scrcpy + SIGO (conectar y ejecutar todo)
echo   [R] Ejecutar SIGO
echo   [0] Salir
echo.
echo  --------------------------------------------------------------
set /p choice="  Selecciona una opcion: "

if "%choice%"=="1" goto INSTALL_FULL
if "%choice%"=="2" goto INSTALL_BASIC
if "%choice%"=="3" goto INSTALL_CPU
if "%choice%"=="4" goto INSTALL_FACE
if "%choice%"=="5" goto INSTALL_PERFORMANCE
if "%choice%"=="6" goto VERIFY
if "%choice%"=="7" goto VENV
if "%choice%"=="8" goto OPENAI_KEY
if "%choice%"=="9" goto SCRCPY_ONLY
if /i "%choice%"=="S" goto SCRCPY_THEN_SIGO
if /i "%choice%"=="R" goto RUN_SIGO
if "%choice%"=="0" goto END
goto MENU

:: ============================================
:: INSTALACION COMPLETA
:: ============================================
:INSTALL_FULL
cls
echo.
echo  ==============================================================
echo           Instalacion Completa - Todas las Funciones
echo  ==============================================================
echo.

call :CHECK_PYTHON
if errorlevel 1 goto MENU

call :CREATE_VENV
call :ACTIVATE_VENV

echo.
echo  [1/4] Instalando dependencias principales...
pip install -r requirements\requirements.txt
if errorlevel 1 (
    echo  [ERROR] Error al instalar dependencias principales
    pause
    goto MENU
)

echo.
echo  [2/4] Instalando reconocimiento facial...
pip install -r requirements\requirements-face.txt
if errorlevel 1 (
    echo  [WARN] Error al instalar reconocimiento facial
)

echo.
echo  [3/4] Instalando paquetes de rendimiento...
pip install -r requirements\requirements-performance.txt
if errorlevel 1 (
    echo  [WARN] Error al instalar paquetes de rendimiento
)

echo.
echo  [4/4] Descargando modelo ArcFace (reconocimiento facial)...
python -c "import os, urllib.request; d=os.path.expanduser('~/.insightface/models/buffalo_l'); os.makedirs(d,exist_ok=True); f=os.path.join(d,'w600k_r50.onnx'); (print('[OK] ArcFace ya descargado') if os.path.exists(f) else (print('Descargando w600k_r50.onnx (~174MB)...'), urllib.request.urlretrieve('https://huggingface.co/deepinsight/insightface/resolve/main/models/buffalo_l/w600k_r50.onnx',f), print('[OK] ArcFace descargado')))" 2>nul
if errorlevel 1 (
    echo  [WARN] No se pudo descargar ArcFace automaticamente
    echo  Se descargara al primer uso del reconocimiento facial
)

echo.
echo  Verificando instalacion...
python -c "import cv2, ultralytics, torch; print('[OK] Instalacion exitosa')"

echo.
echo  ==============================================================
echo           [OK] INSTALACION COMPLETA FINALIZADA
echo  ==============================================================
echo.
echo  Proximos pasos:
echo    1. Configurar OpenAI API Key (Opcion 8)
echo    2. Conectar Scrcpy Wireless (Opcion 9)
echo    3. Ejecutar: Opcion R o S
echo.
pause
goto MENU

:: ============================================
:: INSTALACION BASICA
:: ============================================
:INSTALL_BASIC
cls
echo.
echo  ==============================================================
echo           Instalacion Basica - Sin Reconocimiento Facial
echo  ==============================================================
echo.

call :CHECK_PYTHON
if errorlevel 1 goto MENU

call :CREATE_VENV
call :ACTIVATE_VENV

echo.
echo  Instalando dependencias principales...
pip install -r requirements\requirements.txt
if errorlevel 1 (
    echo  [ERROR] Error al instalar dependencias
    pause
    goto MENU
)

echo.
echo  Verificando instalacion...
python -c "import cv2, ultralytics, torch; print('[OK] Instalacion basica exitosa')"

echo.
echo  [OK] Instalacion basica completada
echo.
pause
goto MENU

:: ============================================
:: INSTALACION CPU
:: ============================================
:INSTALL_CPU
cls
echo.
echo  ==============================================================
echo           Instalacion CPU - Optimizada sin GPU
echo  ==============================================================
echo.

call :CHECK_PYTHON
if errorlevel 1 goto MENU

call :CREATE_VENV
call :ACTIVATE_VENV

echo.
echo  Instalando version CPU de PyTorch y dependencias...
pip install -r requirements\requirements-cpu.txt
if errorlevel 1 (
    echo  [ERROR] Error al instalar dependencias CPU
    pause
    goto MENU
)

echo.
echo  [OK] Instalacion CPU completada
echo.
pause
goto MENU

:: ============================================
:: SOLO RECONOCIMIENTO FACIAL
:: ============================================
:INSTALL_FACE
cls
echo.
echo  ==============================================================
echo           Instalacion - Solo Reconocimiento Facial
echo  ==============================================================
echo.

call :ACTIVATE_VENV

echo.
echo  Instalando paquetes de reconocimiento facial...
pip install -r requirements\requirements-face.txt
if errorlevel 1 (
    echo  [ERROR] Error al instalar reconocimiento facial
    pause
    goto MENU
)

echo.
echo  [OK] Reconocimiento facial instalado
echo.
echo  El modelo ArcFace se descarga automaticamente al primer uso.
echo  Enroll faces via console: save person 1 as Name
echo.
pause
goto MENU

:: ============================================
:: PAQUETES DE RENDIMIENTO
:: ============================================
:INSTALL_PERFORMANCE
cls
echo.
echo  ==============================================================
echo           Instalacion - Paquetes de Rendimiento
echo  ==============================================================
echo.

call :ACTIVATE_VENV

echo.
echo  Instalando paquetes de optimizacion...
pip install -r requirements\requirements-performance.txt
if errorlevel 1 (
    echo  [ERROR] Error al instalar paquetes de rendimiento
    pause
    goto MENU
)

echo.
echo  [OK] Paquetes de rendimiento instalados
echo.
pause
goto MENU

:: ============================================
:: VERIFICAR INSTALACION
:: ============================================
:VERIFY
cls
echo.
echo  ==============================================================
echo                Verificacion de Instalacion
echo  ==============================================================
echo.

call :ACTIVATE_VENV

echo  Verificando entorno Python...
python --version
echo.

echo  Verificando paquetes principales...
python -c "import sys; print('Python:', sys.version)"
python -c "import cv2; print('OpenCV:', cv2.__version__)" 2>nul && echo  [OK] OpenCV || echo  [MISS] OpenCV no instalado
python -c "import torch; print('PyTorch:', torch.__version__)" 2>nul && echo  [OK] PyTorch || echo  [MISS] PyTorch no instalado
python -c "import ultralytics; print('Ultralytics:', ultralytics.__version__)" 2>nul && echo  [OK] Ultralytics || echo  [MISS] Ultralytics no instalado
python -c "import openai; print('OpenAI:', openai.__version__)" 2>nul && echo  [OK] OpenAI || echo  [MISS] OpenAI no instalado

echo.
echo  Verificando paquetes opcionales...
python -c "import onnxruntime; print('ONNX Runtime:', onnxruntime.__version__)" 2>nul && echo  [OK] ONNX Runtime (ArcFace) || echo  [WARN] ONNX Runtime no instalado
python -c "import numba; print('Numba: instalado')" 2>nul && echo  [OK] Numba || echo  [WARN] Numba no instalado

echo.
echo  Verificando archivos del sistema...
if exist "SIGO1.py" (echo  [OK] SIGO1.py) else (echo  [MISS] SIGO1.py no encontrado)
if exist "config.py" (echo  [OK] config.py) else (echo  [MISS] config.py no encontrado)
if exist "yolov8s-pose.pt" (echo  [OK] yolov8s-pose.pt) else (echo  [WARN] yolov8s-pose.pt no encontrado)

echo.
echo  Verificando scrcpy...
if exist "%SCRCPY_EXE%" (echo  [OK] scrcpy v%SCRCPY_VERSION%) else (echo  [WARN] scrcpy no instalado - usa opcion 9)

echo.
echo  --------------------------------------------------------------
echo  Ejecutando validacion de importaciones...
python -c "import cv2, ultralytics, torch; print('[OK] Modulos core OK')" 2>nul
if errorlevel 1 echo  [ERROR] Error en modulos core

echo.
pause
goto MENU

:: ============================================
:: ENTORNO VIRTUAL
:: ============================================
:VENV
cls
echo.
echo  ==============================================================
echo                Gestion de Entorno Virtual
echo  ==============================================================
echo.

if exist ".venv" (
    echo  [INFO] Entorno virtual ya existe en: .venv
    echo.
    set /p recreate="  Deseas recrearlo? (s/N): "
    if /i "!recreate!"=="s" (
        echo  Eliminando entorno anterior...
        rmdir /s /q .venv
        call :CREATE_VENV
    ) else (
        echo.
        echo  Para activar manualmente: .venv\Scripts\activate
    )
) else (
    call :CREATE_VENV
)

echo.
pause
goto MENU

:: ============================================
:: CONFIGURAR OPENAI API KEY
:: ============================================
:OPENAI_KEY
cls
echo.
echo  ==============================================================
echo            Configuracion de OpenAI API Key
echo  ==============================================================
echo.
echo  Esta clave es necesaria para los comandos de voz.
echo  Obtenla en: https://platform.openai.com/api-keys
echo.

set /p api_key="  Ingresa tu OpenAI API Key: "

if "%api_key%"=="" (
    echo  [ERROR] No se ingreso ninguna clave
    pause
    goto MENU
)

echo.
echo  Configurando variable de entorno...
setx OPENAI_API_KEY "%api_key%" >nul

echo.
echo  [OK] API Key configurada exitosamente
echo.
echo  La clave estara disponible en nuevas sesiones de terminal.
echo  Para usarla ahora: set OPENAI_API_KEY=%api_key%
echo.
pause
goto MENU

:: ============================================
:: [9] CONECTAR SCRCPY WIRELESS (solo scrcpy)
:: ============================================
:SCRCPY_ONLY
cls
echo.
echo  ==============================================================
echo            Conectar Scrcpy Wireless (DJI Spark)
echo  ==============================================================
echo.

call :SCRCPY_WIRELESS_SETUP
if errorlevel 1 goto MENU

echo.
echo  -----------------------------------------------------------
echo   SCRCPY RUNNING  (close window or Ctrl+C to stop)
echo   Device: !WIRELESS_DEVICE!
echo  -----------------------------------------------------------
echo.

echo !WIRELESS_DEVICE!> "%~dp0.scrcpy_device"

"%SCRCPY_EXE%" --serial=!WIRELESS_DEVICE! --window-title "scrcpy" --video-bit-rate 12M --max-size 2340 --max-fps 30 --no-control --no-audio --render-driver=opengl

if errorlevel 1 (
    echo.
    echo  [ERROR] scrcpy exited with an error. Re-run to reconnect.
    echo.
)

del "%~dp0.scrcpy_device" >nul 2>&1
echo.
echo  [DONE] scrcpy closed.
pause
goto MENU

:: ============================================
:: [S] SCRCPY + SIGO (connect, launch, run)
:: ============================================
:SCRCPY_THEN_SIGO
cls
echo.
echo  ==============================================================
echo        Scrcpy + SIGO  (conectar y ejecutar todo)
echo  ==============================================================
echo.

REM -- Step 1: Virtual environment -----
if not exist ".venv\Scripts\activate.bat" (
    echo  [ERROR] Entorno virtual no encontrado.
    echo  Ejecuta primero la opcion [7] para crearlo.
    echo.
    pause
    goto MENU
)
echo  [1/4] Activando entorno virtual...
call .venv\Scripts\activate.bat
echo  [OK]  Entorno virtual activo.
echo.

REM -- Step 2: Wireless scrcpy setup ---
echo  [2/4] Configurando scrcpy wireless...
call :SCRCPY_WIRELESS_SETUP
if errorlevel 1 goto MENU
echo.

REM -- Step 3: Launch scrcpy in background ---
echo  [3/4] Lanzando scrcpy en segundo plano...
echo !WIRELESS_DEVICE!> "%~dp0.scrcpy_device"

start "scrcpy" /b "%SCRCPY_EXE%" --serial=!WIRELESS_DEVICE! --window-title "scrcpy" --video-bit-rate 12M --max-size 2340 --max-fps 30 --no-control --no-audio --render-driver=opengl

REM Wait for scrcpy window to appear
echo        Esperando ventana scrcpy...
set "SCRCPY_READY=0"
for /l %%i in (1,1,30) do (
    if !SCRCPY_READY! EQU 0 (
        powershell -Command "if (Get-Process scrcpy -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
        if !errorlevel! EQU 0 (
            set "SCRCPY_READY=1"
        ) else (
            timeout /t 1 >nul
        )
    )
)

if !SCRCPY_READY! EQU 0 (
    echo.
    echo  [ERROR] scrcpy no se inicio a tiempo.
    echo  Intenta la opcion [9] primero para verificar la conexion.
    echo.
    pause
    goto MENU
)

REM Extra seconds for the video feed to stabilize
timeout /t 2 >nul
echo  [OK]  scrcpy corriendo (ventana "scrcpy")
echo.

REM -- Step 4: Run SIGO ---
echo  [4/4] Ejecutando SIGO...
echo.
echo  ==============================================================
echo   scrcpy: corriendo en segundo plano
echo   SIGO:   iniciando...
echo  ==============================================================
echo.

python SIGO1.py

echo.
echo  SIGO ha finalizado.
echo.

REM Kill scrcpy when SIGO exits
taskkill /f /im scrcpy.exe >nul 2>&1
del "%~dp0.scrcpy_device" >nul 2>&1
echo  [DONE] scrcpy cerrado.
pause
goto MENU

:: ============================================
:: EJECUTAR SIGO (solo)
:: ============================================
:RUN_SIGO
cls
echo.
echo  ==============================================================
echo                   Iniciando SIGO...
echo  ==============================================================
echo.
if not exist ".venv\Scripts\activate.bat" (
    echo  [ERROR] Entorno virtual no encontrado.
    echo  Ejecuta primero la opcion [7] para crear el entorno virtual.
    echo.
    pause
    goto MENU
)
echo  Activando entorno virtual...
call .venv\Scripts\activate.bat
echo  Ejecutando SIGO1.py...
echo.
python SIGO1.py
echo.
echo  SIGO ha finalizado.
pause
goto MENU

:: ============================================
:: FUNCIONES AUXILIARES
:: ============================================

:: --- CHECK_PYTHON ---
:CHECK_PYTHON
echo  Verificando Python...
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.12"
    echo  [OK] Python 3.12 encontrado (py launcher)
    exit /b 0
)

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Python no esta instalado o no esta en el PATH
    echo.
    echo  Instala Python 3.12 desde: https://www.python.org/downloads/
    echo  Marca "Add Python to PATH" durante la instalacion
    echo.
    pause
    exit /b 1
)

python -c "import sys; exit(1 if sys.version_info >= (3, 14) else 0)" 2>nul
if errorlevel 1 (
    echo.
    echo  [ERROR] Python 3.14 detectado. Incompatible.
    echo  Instala Python 3.12 o 3.13.
    echo.
    pause
    exit /b 1
)

set "PYTHON_CMD=python"
echo  [OK] Python encontrado
exit /b 0

:: --- CREATE_VENV ---
:CREATE_VENV
echo.
echo  Creando entorno virtual en .venv con !PYTHON_CMD!...
!PYTHON_CMD! -m venv .venv
if errorlevel 1 (
    echo  [ERROR] Error al crear entorno virtual
    pause
    exit /b 1
)
echo  [OK] Entorno virtual creado
echo  Para activar manualmente: .venv\Scripts\activate
exit /b 0

:: --- ACTIVATE_VENV ---
:ACTIVATE_VENV
if exist ".venv\Scripts\activate.bat" (
    echo  Activando entorno virtual...
    call .venv\Scripts\activate.bat
    echo  [OK] Entorno virtual activado
) else (
    echo.
    echo  [WARN] No se encontro entorno virtual
    echo  Ejecuta la opcion 7 del menu para crearlo
    echo.
    set /p create="  Crear ahora? (S/n): "
    if /i not "!create!"=="n" (
        call :CREATE_VENV
        call .venv\Scripts\activate.bat
    ) else (
        pause
        goto MENU
    )
)
exit /b 0

:: ============================================
:: SCRCPY WIRELESS SETUP (shared subroutine)
:: Sets WIRELESS_DEVICE on success.
:: Returns errorlevel 0 on success, 1 on failure.
:: ============================================
:SCRCPY_WIRELESS_SETUP

REM --- Install scrcpy if needed ---
if exist "%SCRCPY_EXE%" (
    echo  [OK] scrcpy found.
) else (
    echo  [INFO] scrcpy not found. Downloading v%SCRCPY_VERSION%...
    set "TEMP_ZIP=%TEMP%\scrcpy-temp.zip"
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%SCRCPY_URL%' -OutFile '!TEMP_ZIP!'}"
    if errorlevel 1 (
        echo  [ERROR] Download failed. Get it manually: %SCRCPY_URL%
        pause
        exit /b 1
    )
    echo  [OK] Downloaded. Extracting...
    powershell -Command "& {Expand-Archive -Path '!TEMP_ZIP!' -DestinationPath '%~dp0' -Force}"
    for /d %%i in ("%~dp0scrcpy-win64-v*") do (
        if exist "%%i" move "%%i" "%SCRCPY_DIR%" >nul 2>&1
    )
    del "!TEMP_ZIP!" >nul 2>&1
    if not exist "%SCRCPY_EXE%" (
        echo  [ERROR] Scrcpy installation failed.
        pause
        exit /b 1
    )
    echo  [OK] scrcpy installed.
)
echo.

REM --- Check if already connected wirelessly ---
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
    echo  [OK] Already connected wirelessly: !WIRELESS_DEVICE!
    exit /b 0
)

if defined USB_DEVICE goto :scrcpy_phone_found

REM --- Wait for USB phone ---
echo   Plug your phone into this PC via USB cable.
echo   (Temporarily, to get the IP and enable wireless ADB)
echo.

:scrcpy_wait_usb
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
    goto :scrcpy_wait_usb
)

:scrcpy_phone_found
for /f "delims=" %%i in ('"%ADB_EXE%" -s !USB_DEVICE! shell getprop ro.product.model 2^>nul') do set "PHONE_MODEL=%%i"
echo  [OK] Phone: !PHONE_MODEL! (!USB_DEVICE!)
echo.

REM --- Enable wireless ADB ---
echo  [INFO] adb tcpip %ADB_PORT%
"%ADB_EXE%" -s !USB_DEVICE! tcpip %ADB_PORT%
if !errorlevel! NEQ 0 (
    echo  [ERROR] Failed. Make sure USB debugging is authorized.
    pause
    exit /b 1
)
timeout /t 2 >nul
echo  [OK] Wireless ADB enabled.
echo.

REM --- Get phone IP from the phone itself ---
echo  [INFO] adb shell ip route
set "PHONE_IP="
for /f "tokens=*" %%r in ('"%ADB_EXE%" -s !USB_DEVICE! shell ip route 2^>nul') do (
    if not defined PHONE_IP (
        for /f "tokens=9" %%a in ("%%r") do (
            set "PHONE_IP=%%a"
        )
    )
)

if not defined PHONE_IP (
    echo  [WARN] Could not get IP from phone.
    set /p "PHONE_IP=  Enter phone IP manually: "
)

echo  [OK] Phone IP: !PHONE_IP!
echo.

REM --- Connect wirelessly ---
echo  [INFO] adb connect !PHONE_IP!:%ADB_PORT%
"%ADB_EXE%" connect !PHONE_IP!:%ADB_PORT%
timeout /t 2 >nul

REM Verify connection
"%ADB_EXE%" devices 2>nul | findstr /C:"!PHONE_IP!:%ADB_PORT!" | findstr /C:"device" >nul
if errorlevel 1 (
    echo  [WARN] Not connected yet, retrying...
    timeout /t 3 >nul
    "%ADB_EXE%" connect !PHONE_IP!:%ADB_PORT%
    timeout /t 2 >nul
)

set "WIRELESS_DEVICE=!PHONE_IP!:%ADB_PORT%"
echo.
echo  [OK] Connected: !WIRELESS_DEVICE!
echo.
echo  -----------------------------------------------------------
echo   Now unplug the phone from USB and plug into DJI Controller
echo   Then connect this PC's WiFi to the phone's hotspot.
echo.
echo   Press any key when ready...
echo  -----------------------------------------------------------
pause >nul

exit /b 0

:: ============================================
:: SALIR
:: ============================================
:END
cls
echo.
echo  ==============================================================
echo                  Gracias por usar SIGO
echo  ==============================================================
echo.
echo  Para iniciar SIGO:
echo    1. Activa el entorno: .venv\Scripts\activate
echo    2. Ejecuta: python SIGO1.py
echo.
echo  Documentacion: docs\README.md
echo.
timeout /t 3 >nul
exit /b 0
