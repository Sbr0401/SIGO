@echo off
chcp 65001 >nul
title SIGO - Launcher with Local LLM (Ollama)

:: ====================================================
:: SIGO LAUNCHER
:: Automates Ollama + SIGO startup
:: ====================================================

:: 1. Check if Ollama is installed
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Ollama not found!
    echo Please install Ollama from https://ollama.com/download
    echo.
    pause
    exit /b 1
)

:: 2. Ensure Ollama Server is Running
echo [INFO] Checking Ollama server status...
tasklist | findstr "ollama.exe" >nul
if %errorlevel% neq 0 (
    echo [INFO] Starting Ollama server...
    start "Ollama Server" /MIN ollama serve
    echo [INFO] Waiting for server to initialize...
    timeout /t 5 >nul
) else (
    echo [OK] Ollama server is running.
)

:: 3. Prepare Model (Idempotent pull is safer than list check)
set MODEL_NAME=llama3.1
echo [INFO] Ensuring model '%MODEL_NAME%' is ready...
echo [INFO] ( If this is the first time, it will download ~4.7GB )
ollama pull %MODEL_NAME%

:: 4. Activate Python Environment
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run 'setup_sigo.bat' first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat

:: 5. Configure Environment Variables for Local LLM
echo.
echo [INFO] Configuring SIGO to use Local LLM...
set OPENAI_BASE_URL=http://localhost:11434/v1
set OPENAI_MODEL=%MODEL_NAME%
set OPENAI_API_KEY=ollama
echo [INFO] API Endpoint: %OPENAI_BASE_URL%
echo [INFO] Model: %OPENAI_MODEL%
echo.

:: 6. Launch SIGO (Use 'py' launcher to ensure correct version)
echo [INFO] Starting SIGO...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" SIGO1.py
) else (
    echo [ERROR] Python executable not found in .venv!
    pause
)

:: 7. Cleanup on exit
echo.
echo [INFO] SIGO closed.
pause
