@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================
:: SIGO - Script de Instalación Automática
:: ============================================

color 0A
title SIGO - Instalación y Configuración

:MENU
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║          SIGO - Sistema de Instalación Automática             ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo  [1] Instalación Completa (Todo incluido)
echo  [2] Instalación Básica (Sin reconocimiento facial)
echo  [3] Instalación CPU (Optimizada para CPU, sin GPU)
echo  [4] Solo Reconocimiento Facial (agregar a instalación existente)
echo  [5] Solo Paquetes de Rendimiento
echo  [6] Verificar Instalación
echo  [7] Crear/Activar Entorno Virtual
echo  [8] Configurar OpenAI API Key
echo  [9] Configurar Scrcpy (Android)
echo  [R] Ejecutar SIGO (Run)
echo  [0] Salir
echo.
echo ────────────────────────────────────────────────────────────────
set /p choice="Selecciona una opción: "

if "%choice%"=="1" goto INSTALL_FULL
if "%choice%"=="2" goto INSTALL_BASIC
if "%choice%"=="3" goto INSTALL_CPU
if "%choice%"=="4" goto INSTALL_FACE
if "%choice%"=="5" goto INSTALL_PERFORMANCE
if "%choice%"=="6" goto VERIFY
if "%choice%"=="7" goto VENV
if "%choice%"=="8" goto OPENAI_KEY
if "%choice%"=="9" goto SCRCPY
if /i "%choice%"=="R" goto RUN_SIGO
if "%choice%"=="0" goto END
goto MENU

:: ============================================
:: INSTALACIÓN COMPLETA
:: ============================================
:INSTALL_FULL
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              Instalación Completa - Todas las Funciones        ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

call :CHECK_PYTHON
if errorlevel 1 goto MENU

call :CREATE_VENV
call :ACTIVATE_VENV

echo.
echo [1/4] Instalando dependencias principales...
pip install -r requirements\requirements.txt
if errorlevel 1 (
    echo ❌ Error al instalar dependencias principales
    pause
    goto MENU
)

echo.
echo [2/4] Instalando reconocimiento facial...
pip install -r requirements\requirements-face.txt
if errorlevel 1 (
    echo ⚠️  Advertencia: Error al instalar reconocimiento facial
)

echo.
echo [3/4] Instalando paquetes de rendimiento...
pip install -r requirements\requirements-performance.txt
if errorlevel 1 (
    echo ⚠️  Advertencia: Error al instalar paquetes de rendimiento
)

echo.
echo [4/4] Verificando instalación...
python -c "import cv2, ultralytics, torch; print('✅ Instalación exitosa')"

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              ✅ INSTALACIÓN COMPLETA FINALIZADA                ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo Próximos pasos:
echo   1. Configurar OpenAI API Key (Opción 8 del menú)
echo   2. (Opcional) Configurar Scrcpy para Android (Opción 9)
echo   3. Ejecutar: python SIGO1.py
echo.
pause
goto MENU

:: ============================================
:: INSTALACIÓN BÁSICA
:: ============================================
:INSTALL_BASIC
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              Instalación Básica - Sin Reconocimiento Facial    ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

call :CHECK_PYTHON
if errorlevel 1 goto MENU

call :CREATE_VENV
call :ACTIVATE_VENV

echo.
echo Instalando dependencias principales...
pip install -r requirements\requirements.txt
if errorlevel 1 (
    echo ❌ Error al instalar dependencias
    pause
    goto MENU
)

echo.
echo Verificando instalación...
python -c "import cv2, ultralytics, torch; print('✅ Instalación básica exitosa')"

echo.
echo ✅ Instalación básica completada
echo.
pause
goto MENU

:: ============================================
:: INSTALACIÓN CPU
:: ============================================
:INSTALL_CPU
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║           Instalación CPU - Optimizada sin GPU                 ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

call :CHECK_PYTHON
if errorlevel 1 goto MENU

call :CREATE_VENV
call :ACTIVATE_VENV

echo.
echo Instalando versión CPU de PyTorch y dependencias...
pip install -r requirements\requirements-cpu.txt
if errorlevel 1 (
    echo ❌ Error al instalar dependencias CPU
    pause
    goto MENU
)

echo.
echo ✅ Instalación CPU completada
echo.
pause
goto MENU

:: ============================================
:: SOLO RECONOCIMIENTO FACIAL
:: ============================================
:INSTALL_FACE
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║           Instalación - Solo Reconocimiento Facial             ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

call :ACTIVATE_VENV

echo.
echo Instalando paquetes de reconocimiento facial...
pip install -r requirements\requirements-face.txt
if errorlevel 1 (
    echo ❌ Error al instalar reconocimiento facial
    pause
    goto MENU
)

echo.
echo ✅ Reconocimiento facial instalado
echo.
echo El modelo ArcFace se descarga automaticamente al primer uso.
echo Enroll faces via console: save person 1 as Name
echo.
pause
goto MENU

:: ============================================
:: PAQUETES DE RENDIMIENTO
:: ============================================
:INSTALL_PERFORMANCE
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║           Instalación - Paquetes de Rendimiento                ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

call :ACTIVATE_VENV

echo.
echo Instalando paquetes de optimización...
pip install -r requirements\requirements-performance.txt
if errorlevel 1 (
    echo ❌ Error al instalar paquetes de rendimiento
    pause
    goto MENU
)

echo.
echo ✅ Paquetes de rendimiento instalados
echo.
pause
goto MENU

:: ============================================
:: VERIFICAR INSTALACIÓN
:: ============================================
:VERIFY
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              Verificación de Instalación                       ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

call :ACTIVATE_VENV

echo Verificando entorno Python...
python --version
echo.

echo Verificando paquetes principales...
python -c "import sys; print('Python:', sys.version)"
python -c "import cv2; print('OpenCV:', cv2.__version__)" 2>nul && echo ✅ OpenCV || echo ❌ OpenCV no instalado
python -c "import torch; print('PyTorch:', torch.__version__)" 2>nul && echo ✅ PyTorch || echo ❌ PyTorch no instalado
python -c "import ultralytics; print('Ultralytics:', ultralytics.__version__)" 2>nul && echo ✅ Ultralytics || echo ❌ Ultralytics no instalado
python -c "import openai; print('OpenAI:', openai.__version__)" 2>nul && echo ✅ OpenAI || echo ❌ OpenAI no instalado

echo.
echo Verificando paquetes opcionales...
python -c "import onnxruntime; print('ONNX Runtime:', onnxruntime.__version__)" 2>nul && echo ✅ ONNX Runtime (reconocimiento facial ArcFace) || echo ⚠️  ONNX Runtime no instalado (reconocimiento facial)
python -c "import numba; print('Numba:', 'instalado')" 2>nul && echo ✅ Numba || echo ⚠️  Numba no instalado

echo.
echo Verificando archivos del sistema...
if exist "SIGO1.py" (echo ✅ SIGO1.py) else (echo ❌ SIGO1.py no encontrado)
if exist "config.py" (echo ✅ config.py) else (echo ❌ config.py no encontrado)
if exist "yolov8s-pose.pt" (echo ✅ yolov8s-pose.pt) else (echo ⚠️  yolov8s-pose.pt no encontrado)

echo.
echo ────────────────────────────────────────────────────────────────
echo Ejecutando validación de importaciones...
python -c "import cv2, ultralytics, torch; print('✅ Módulos core OK')" 2>nul
if errorlevel 1 echo ❌ Error en módulos core

echo.
pause
goto MENU

:: ============================================
:: ENTORNO VIRTUAL
:: ============================================
:VENV
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              Gestión de Entorno Virtual                        ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

if exist ".venv" (
    echo ℹ️  Entorno virtual ya existe en: .venv
    echo.
    set /p recreate="¿Deseas recrearlo? (s/N): "
    if /i "!recreate!"=="s" (
        echo Eliminando entorno anterior...
        rmdir /s /q .venv
        call :CREATE_VENV
    ) else (
        echo.
        echo Para activar el entorno virtual, ejecuta:
        echo   .venv\Scripts\activate
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
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              Configuración de OpenAI API Key                   ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo Esta clave es necesaria para los comandos de voz.
echo Obtén tu clave en: https://platform.openai.com/api-keys
echo.

set /p api_key="Ingresa tu OpenAI API Key: "

if "%api_key%"=="" (
    echo ❌ No se ingresó ninguna clave
    pause
    goto MENU
)

echo.
echo Configurando variable de entorno...
setx OPENAI_API_KEY "%api_key%" >nul

echo.
echo ✅ API Key configurada exitosamente
echo.
echo La clave estará disponible en nuevas sesiones de terminal.
echo Para usarla ahora, ejecuta: set OPENAI_API_KEY=%api_key%
echo.
pause
goto MENU

:: ============================================
:: CONFIGURAR SCRCPY
:: ============================================
:SCRCPY
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              Configuración de Scrcpy (Android)                 ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo Scrcpy permite usar la cámara de tu teléfono Android.
echo.
echo Pasos:
echo   1. Habilita "Depuración USB" en tu Android
echo   2. Conecta el teléfono por USB
echo   3. Acepta la autorización en el teléfono
echo.

set /p continue="¿Continuar con la instalación? (S/n): "
if /i "%continue%"=="n" goto MENU

echo.
echo Descargando e instalando Scrcpy...

if exist "setup_scrcpy.bat" (
    call setup_scrcpy.bat
    echo.
    echo ✅ Instalación de Scrcpy completada
) else (
    echo Descargando Scrcpy desde GitHub...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://github.com/Genymobile/scrcpy/releases/download/v2.3.1/scrcpy-win64-v2.3.1.zip' -OutFile 'scrcpy.zip'}"
    powershell -Command "& {Expand-Archive -Path 'scrcpy.zip' -DestinationPath '.' -Force}"
    del scrcpy.zip
    echo ✅ Scrcpy descargado y extraído
)

echo.
echo Para usar la cámara Android en SIGO:
echo   1. Conecta el teléfono por USB
echo   2. Ejecuta: scrcpy-win64-v2.3.1\scrcpy.exe
echo   3. En SIGO, selecciona "Android" como fuente de video
echo.
pause
goto MENU

:: ============================================
:: FUNCIONES AUXILIARES
:: ============================================

:CHECK_PYTHON
echo Verificando Python...
:: Intentar usar 'py -3.12' primero (recomendado)
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.12"
    echo ✅ Python 3.12 encontrado (py launcher)
    exit /b 0
)

:: Intentar 'python' normal
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ❌ Python no está instalado o no está en el PATH
    echo.
    echo Por favor instala Python 3.12 desde: https://www.python.org/downloads/
    echo Asegúrate de marcar "Add Python to PATH" durante la instalación
    echo.
    pause
    exit /b 1
)

:: Verificar que versión NO sea 3.14 (incompatible)
python -c "import sys; exit(1 if sys.version_info >= (3, 14) else 0)" 2>nul
if errorlevel 1 (
    echo.
    echo ❌ Python 3.14 detectado. Esta versión es demasiado nueva e incompatible.
    echo Por favor instala Python 3.12 o 3.13.
    echo.
    pause
    exit /b 1
)

set "PYTHON_CMD=python"
echo ✅ Python encontrado
exit /b 0

:CREATE_VENV
echo.
echo Creando entorno virtual en .venv con !PYTHON_CMD!...
!PYTHON_CMD! -m venv .venv
if errorlevel 1 (
    echo ❌ Error al crear entorno virtual
    pause
    exit /b 1
)
echo ✅ Entorno virtual creado
echo.
echo Para activarlo manualmente: .venv\Scripts\activate
exit /b 0

:ACTIVATE_VENV
if exist ".venv\Scripts\activate.bat" (
    echo Activando entorno virtual...
    call .venv\Scripts\activate.bat
    echo ✅ Entorno virtual activado
) else (
    echo.
    echo ⚠️  No se encontró entorno virtual
    echo Ejecuta la opción 7 del menú para crearlo
    echo.
    set /p create="¿Crear ahora? (S/n): "
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
:: EJECUTAR SIGO
:: ============================================
:RUN_SIGO
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              Iniciando SIGO...                                  ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Entorno virtual no encontrado.
    echo Ejecuta primero la opción [7] para crear el entorno virtual.
    echo.
    pause
    goto MENU
)
echo Activando entorno virtual...
call .venv\Scripts\activate.bat
echo Ejecutando SIGO1.py...
echo.
python SIGO1.py
echo.
echo SIGO ha finalizado.
pause
goto MENU

:: ============================================
:: SALIR
:: ============================================
:END
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              Gracias por usar SIGO                             ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo Para iniciar SIGO:
echo   1. Activa el entorno: .venv\Scripts\activate
echo   2. Ejecuta: python SIGO1.py
echo.
echo Documentación completa en: docs\README.md
echo.
timeout /t 3 >nul
exit /b 0
