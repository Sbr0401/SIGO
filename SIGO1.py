#!/usr/bin/env python3
"""
SIGO - Sistema Integrado de Gestión de Objetivo
AI-Powered ArUco Marker Navigation System
Version: 2.0 - Refactored
"""
import cv2
import numpy as np
import re
import time
import threading
from collections import OrderedDict, deque
from queue import Queue, Full, Empty
from ultralytics import YOLO
from openai import OpenAI
import os
import keyboard
from faster_whisper import WhisperModel
import sounddevice as sd
from scipy.io.wavfile import write
import tempfile
import torch
import socket
import asyncio
import ctypes
import math
import subprocess
import shutil
from typing import Optional, List
import numpy.typing as npt
try:
    import win32gui
    import win32ui
    import win32con
    SCRCPY_AVAILABLE = True
except ImportError:
    SCRCPY_AVAILABLE = False

# Declare DPI awareness so GetClientRect returns real pixels (not scaled)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-Monitor DPI Aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()    # Fallback (System DPI Aware)
    except Exception:
        pass

import serial
import serial.tools.list_ports

# Directory where this script lives (for resolving model paths)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Early GPU detection (done once at import time)
_HAS_CUDA = torch.cuda.is_available()
if _HAS_CUDA:
    print(f"✅ GPU detectada: {torch.cuda.get_device_name(0)}")
else:
    print("ℹ️  No NVIDIA GPU — usando CPU para inferencia")

# Text-to-Speech for audio feedback (F4)
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# Facial recognition system (ArcFace via ONNX Runtime)
try:
    from face_recognition_insightface import LiveFaceRecognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("⚠️ Face recognition not available. Ensure onnxruntime-gpu and ArcFace model are installed.")

# Import centralized configuration
try:
    from config import Config
except ImportError:
    print("⚠️ config.py no encontrado, usando valores por defecto")
    # Fallback to inline config if config.py missing
    class Config:
        class Hardware:
            SERIAL_PORT = 'auto'
            SERIAL_BAUD = 9600
            SERIAL_TIMEOUT = 1
            SERIAL_RECONNECT_GRACE = 15
            CAMERA_IP = "192.168.165.106"
            VEHICLE_IP = "192.168.165.76"
            ESP_PORT = 5555
        class AI:
            OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "ollama")
            OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", None)
            OPENAI_MODEL = "gpt-4o-mini"
            OPENAI_TEMPERATURE = 0.1
            OPENAI_MAX_TOKENS = 10
            WHISPER_MODEL_SIZE = "tiny"
            WHISPER_LANGUAGE = "es"
            WHISPER_SAMPLE_RATE = 16000
            WHISPER_DURATION = 4
            YOLO_MODEL = 'yolo11n.pt'
            YOLO_CONFIDENCE = 0.5
            USE_POSE_DISTANCE = True
            POSE_MODEL = 'yolov8s-pose.pt'
            USE_ARUCO_MARKERS = False
            USE_FACE_RECOGNITION = True
            FACE_DATABASE_DIR = 'face_database'
            FACE_RECOGNITION_THRESHOLD = 0.35
            FACE_MODEL_PATH = os.path.expanduser('~/.insightface/models/buffalo_l/w600k_r50.onnx')
            FOCAL_LENGTH_PIX = None
            @staticmethod
            def get_focal_length(calibration_file=None):
                return None
        class Navigation:
            DISTANCE_TARGET = 1.5
            DISTANCE_CORRECTION = 1.0
            ROTATION_THRESHOLD = 5
            FAST_SPEED_THRESHOLD = 1.0
            MARKER_LOST_TIMEOUT = 3.0
            MARKER_EXPIRE_TIME = 2.0
            DETECTION_RADIUS_SCALE = 2.0
            NAVIGATION_UPDATE_RATE = 0.5
            MANUAL_SEND_RATE = 0.5
        class Vision:
            ARUCO_MARKER_SIZE = 0.20
            ROI_EXPANSION_SCALE = 1.2
            SMOOTH_WINDOW_SIZE = 5
            GAMMA_CORRECTION = 1.2
        class Source:
            SOURCES = {
                "default": {"calibration": "calibration/calINSPIRO.npz", "detection_interval": 5, "target_fps": 30, "control": "wifi"},
                "scrcpy": {"calibration": "calibration/calINSPIRO.npz", "detection_interval": 5, "target_fps": 30, "control": "serial"},
                "stream": {"calibration": "calibration/calINSPIRO.npz", "detection_interval": 1, "target_fps": 15, "control": "wifi"},
            }
        class UI:
            OUTPUT_WIDTH = 1280
            OUTPUT_HEIGHT = 720
            VIDEO_WIDTH_RATIO = 0.7
            CONSOLE_WIDTH_RATIO = 0.3
            INPUT_HEIGHT = 40
            MAX_CONSOLE_LINES = 100
            MAX_COMMAND_HISTORY = 50
        class Keybinds:
            KEY_EXIT = 9
            KEY_BACKSPACE = 8
            KEY_ENTER = 13
            KEY_VOICE_RECORD = '3'
            KEY_CANCEL_NAV = '5'
            KEY_SAFE_MODE = ord('6')
            KEY_FACE_RECOGNITION = ord('4')
            KEY_GESTURE_MODE = ord('8')
            KEY_MANUAL_TOGGLE = '7'
            KEY_MANUAL_EXIT = '7'
        class Performance:
            FRAME_QUEUE_SIZE = 1
            FRAMERATE_MODE = 'auto'
        class Debug:
            SHOW_VIDEO_INFO = False
            VERBOSE_LOGGING = False

# ==========================
#  CONFIG WHISPER / AUDIO
# ==========================
WHISPER_MODEL = None  # Lazy load
WHISPER_USE_CUDA = _HAS_CUDA
WHISPER_SAMPLE_RATE = getattr(Config.AI, 'WHISPER_SAMPLE_RATE', 16000)

def get_whisper_model():
    """Lazy load Whisper model on first use (faster-whisper version)"""
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        print("🧠 Cargando modelo Whisper (primera vez - faster-whisper)...")
        model_size = getattr(Config.AI, 'WHISPER_MODEL_SIZE', 'tiny')
        device = "cuda" if WHISPER_USE_CUDA else "cpu"
        compute_type = "float16" if WHISPER_USE_CUDA else "int8"
        WHISPER_MODEL = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("✅ Modelo Whisper listo (4-8x más rápido!)")
    return WHISPER_MODEL

# ==========================
#  CONFIG SERIAL/WIFI
# ==========================
PUERTO = getattr(Config.Hardware, 'SERIAL_PORT', 'COM8')
BAUD   = getattr(Config.Hardware, 'SERIAL_BAUD', 9600)

CamIP = getattr(Config.Hardware, 'CAMERA_IP', '192.168.165.106')

def detect_phone_gateway():
    """Auto-detect phone hotspot IP from WiFi gateway (Windows)."""
    try:
        import subprocess
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             '(Get-NetIPConfiguration | Where-Object { $_.InterfaceAlias -match "Wi-Fi|WiFi|Wireless|WLAN" -and $_.IPv4DefaultGateway } | Select-Object -First 1).IPv4DefaultGateway.NextHop'],
            capture_output=True, text=True, timeout=10
        )
        ip = result.stdout.strip()
        if ip and ip[0].isdigit():
            return ip
    except Exception:
        pass
    return None
CarIP = getattr(Config.Hardware, 'VEHICLE_IP', '192.168.165.76')
ESP_PORT = getattr(Config.Hardware, 'ESP_PORT', 5555)
RECONNECT_GRACE = getattr(Config.Hardware, 'SERIAL_RECONNECT_GRACE', 15)

def resolve_face_database_dir() -> str:
    """Resolve a stable face database path independent of current working directory.

    Priority:
    1) Existing configured path from current CWD (legacy behavior)
    2) Existing workspace-root path (one level above SIGO-FINAL)
    3) Existing SIGO-FINAL local path
    4) Fallback to workspace-root path (created by face system if missing)
    """
    configured = getattr(getattr(Config, 'AI', None), 'FACE_DATABASE_DIR', 'face_database')
    if os.path.isabs(configured):
        return configured

    script_dir = os.path.dirname(os.path.abspath(__file__))            # .../SIGO-FINAL
    workspace_root = os.path.dirname(script_dir)                       # .../SIGOOOOO

    candidates = [
        os.path.abspath(configured),
        os.path.join(workspace_root, configured),
        os.path.join(script_dir, configured),
    ]

    for path in candidates:
        face_db_file = os.path.join(path, 'face_db.pkl')
        if os.path.exists(face_db_file):
            return path

    for path in candidates:
        if os.path.isdir(path) and len(os.listdir(path)) > 0:
            return path

    return os.path.join(workspace_root, configured)

# ==========================
#  TTS (TEXT-TO-SPEECH) ENGINE
# ==========================
_tts_queue: Queue = Queue(maxsize=10)
_tts_engine = None
_tts_thread_started = False

def _tts_worker():
    """Background thread: reads text from _tts_queue and speaks it."""
    global _tts_engine
    try:
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty('rate', 170)   # Words per minute
        _tts_engine.setProperty('volume', 0.9)
        # Try to pick a female voice for variety
        voices = _tts_engine.getProperty('voices')
        for v in voices:
            if 'female' in v.name.lower() or 'zira' in v.name.lower():
                _tts_engine.setProperty('voice', v.id)
                break
    except Exception as e:
        print(f"[TTS] Init failed: {e}")
        return

    while True:
        try:
            text = _tts_queue.get()
            if text is None:
                break  # Poison pill
            _tts_engine.say(text)
            _tts_engine.runAndWait()
        except Exception:
            pass  # Don't crash the TTS thread

def _tts_shutdown():
    """Cleanly stop the TTS engine to avoid pyttsx3 DriverProxy.__del__ error."""
    global _tts_engine
    if _tts_thread_started:
        try:
            _tts_queue.put_nowait(None)  # Poison pill to stop worker
        except Full:
            pass
    if _tts_engine is not None:
        try:
            _tts_engine.stop()
        except Exception:
            pass
        _tts_engine = None

def tts_speak(text: str):
    """Enqueue text for TTS playback (non-blocking). Drops if queue full."""
    global _tts_thread_started
    if not TTS_AVAILABLE:
        return
    if not _tts_thread_started:
        _tts_thread_started = True
        t = threading.Thread(target=_tts_worker, daemon=True)
        t.start()
    try:
        _tts_queue.put_nowait(text)
    except Full:
        pass  # Drop oldest-intent rather than blocking

# ==========================
#  ARDUINO AUTO-DETECT & PROTOCOL
# ==========================
def detect_arduino_port():
    """Auto-detect Arduino Nano COM port by scanning serial ports.
    Nano clones typically use CH340; official ones use FTDI or ATmega16U2."""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        # Priority 1: official Arduino VIDs (ATmega16U2 on genuine Nano)
        ARDUINO_VIDS = ['2341', '2a03']           # Arduino SA, Arduino SRL
        # Priority 2: USB-serial chips common on Nano clones
        #   1a86 = CH340/CH341 (most common Nano clone chip)
        #   0403 = FTDI FT232RL (older genuine Nano)
        #   10c4 = CP210x (rare)
        CHIP_VIDS    = ['1a86', '0403', '10c4']
        DESC_HINTS   = ['arduino', 'nano', 'ch340', 'ch341', 'ft232',
                        'ftdi', 'cp210', 'usb serial', 'usb-serial']
        for port in ports:
            hwid = (port.hwid or '').lower()
            if any(vid in hwid for vid in ARDUINO_VIDS):
                return port.device
        for port in ports:
            desc = (port.description or '').lower()
            hwid = (port.hwid or '').lower()
            if any(vid in hwid for vid in CHIP_VIDS) or any(h in desc for h in DESC_HINTS):
                return port.device
        # Fallback: first available COM port that isn't COM1
        for port in ports:
            if port.device.upper() != 'COM1':
                return port.device
    except Exception:
        pass
    return None

def encode_arduino_pair(ccw=0, cw=0, up=0, down=0, fwd=0, bwd=0, left=0, right=0):
    """Encode 8 channels with magnitude levels (0-3) into 2-byte Arduino protocol.

    Bit layout (same bit position across b1 and b2):
      0: CCW rotation    1: CW rotation
      2: Up              3: Down
      4: Forward          5: Backward
      6: Strafe left     7: Strafe right

    Each channel N is encoded across b1[N] and b2[N]:
      mag 0  → b1=0 b2=0  (off)
      mag 1  → b1=1 b2=0  (gentle)
      mag 2  → b1=0 b2=1  (medium)
      mag 3  → b1=1 b2=1  (strong)
    """
    channels = [ccw, cw, up, down, fwd, bwd, left, right]
    b1 = 0
    b2 = 0
    for i, mag in enumerate(channels):
        mag = max(0, min(3, int(mag)))
        if mag & 1:          # low bit of magnitude → b1
            b1 |= (1 << i)
        if mag & 2:          # high bit of magnitude → b2
            b2 |= (1 << i)
    return b1, b2

# --- Adaptador unificado de control (Serial o WiFi) ---
class ControlLink:
    def __init__(self, mode: str, serial_port='auto', serial_baud=9600,
                 serial_timeout=1, wifi_ip=None, wifi_port=None,
                 reconnect_grace=15):
        """
        mode: 'serial' o 'wifi'
        serial_port: COM port or 'auto' to scan for Arduino
        reconnect_grace: seconds to attempt reconnection before giving up
        """
        self.mode = mode
        self.serial_port = serial_port
        self.serial_baud = serial_baud
        self.serial_timeout = serial_timeout
        self.wifi_ip = wifi_ip
        self.wifi_port = wifi_port
        self.reconnect_grace = reconnect_grace

        self._ser = None   # serial.Serial()
        self._sock = None  # socket.socket()
        self._resolved_port = None  # actual COM port in use

    def _resolve_port(self):
        """Resolve 'auto' to an actual COM port, or use the configured one."""
        if self.serial_port.lower() == 'auto':
            port = detect_arduino_port()
            if not port:
                raise RuntimeError(
                    "No se detectó Arduino en ningún puerto COM.\n"
                    "  - Verifica que el cable USB está conectado\n"
                    "  - Verifica que el driver (CH340/FTDI) está instalado\n"
                    "  - O configura SERIAL_PORT manualmente en config.py"
                )
            return port
        return self.serial_port

    def open(self):
        if self.mode == 'serial':
            self._resolved_port = self._resolve_port()
            if self._ser is None:
                self._ser = serial.Serial()
            self._ser.port = self._resolved_port
            self._ser.baudrate = self.serial_baud
            self._ser.timeout = self.serial_timeout
            if not self._ser.is_open:
                self._ser.open()
            print(f"[CTRL] Serial abierto en {self._ser.port}@{self._ser.baudrate}")

        elif self.mode == 'wifi':
            try:
                if self._sock is not None:
                    self._sock.getpeername()
                else:
                    raise OSError("No socket")
            except Exception:
                if self._sock is not None:
                    try:
                        self._sock.close()
                    except Exception:
                        pass
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(3)
                self._sock.connect((self.wifi_ip, self.wifi_port))
            print(f"[CTRL] WiFi conectado a {self.wifi_ip}:{self.wifi_port}")

    def send(self, b1: int, b2: int = 0):
        """Send a 2-byte command pair to the Arduino.
        b1, b2 encode channel magnitudes (see encode_arduino_pair).
        """
        b1 = int(b1) & 0xFF
        b2 = int(b2) & 0xFF
        if self.mode == 'serial':
            if not self._ser or not self._ser.is_open:
                raise RuntimeError("Serial no abierto - revisa conexión USB")
            try:
                self._ser.write(bytes([b1, b2]))
                self._ser.flush()
            except (serial.SerialException, OSError) as e:
                # Attempt reconnection
                if self._try_reconnect():
                    self._ser.write(bytes([b1, b2]))
                    self._ser.flush()
                else:
                    raise RuntimeError(f"Arduino desconectado y no se pudo reconectar en {self.reconnect_grace}s: {e}")

        elif self.mode == 'wifi':
            if not self._sock:
                raise RuntimeError("Socket no abierto - revisa conexión WiFi")
            try:
                self._sock.sendall(bytes([b1, b2]))
            except socket.timeout:
                raise RuntimeError("Timeout WiFi - ESP no responde")
            except (BrokenPipeError, ConnectionResetError) as e:
                raise RuntimeError(f"Conexión WiFi perdida: {e}")
            except socket.error as e:
                raise RuntimeError(f"Error de red: {e}")

    def _try_reconnect(self):
        """Attempt to reconnect to the Arduino within the grace period.
        Scans for the port again in case it moved to a different COM."""
        print(f"[CTRL] Arduino desconectado. Intentando reconectar ({self.reconnect_grace}s)...")
        start = time.time()
        attempt = 0
        while time.time() - start < self.reconnect_grace:
            attempt += 1
            remaining = self.reconnect_grace - (time.time() - start)
            try:
                # Close stale handle
                if self._ser and self._ser.is_open:
                    try:
                        self._ser.close()
                    except Exception:
                        pass
                # Re-detect port (may have changed COM number)
                port = detect_arduino_port() if self.serial_port.lower() == 'auto' else self.serial_port
                if port:
                    self._ser = serial.Serial()
                    self._ser.port = port
                    self._ser.baudrate = self.serial_baud
                    self._ser.timeout = self.serial_timeout
                    self._ser.open()
                    self._resolved_port = port
                    print(f"[CTRL] Reconectado en {port} (intento {attempt}, {remaining:.0f}s restantes)")
                    return True
            except Exception:
                pass
            time.sleep(1)
        elapsed = time.time() - start
        print(f"[CTRL] No se pudo reconectar en {elapsed:.0f}s ({attempt} intentos)")
        return False

    def close(self):
        """Send stop command (0,0) and close the link."""
        try:
            self.send(0, 0)
            time.sleep(0.05)
        except Exception:
            pass

        if self.mode == 'serial':
            if self._ser and self._ser.is_open:
                self._ser.close()
                print(f"[CTRL] Serial cerrado ({self._resolved_port})")
        elif self.mode == 'wifi':
            if self._sock:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self._sock.close()
                print("[CTRL] Socket WiFi cerrado")
        self._ser = None
        self._sock = None
        self._resolved_port = None

# Instancia global que configuramos en __main__ según la fuente
control = None

# ==========================
# ==========================
#  CONFIGURA LLM (Manual/Auto)
# ==========================
def configure_llm_mode(choice="auto"):
    """
    Configures the LLM backend.
    choice: "local" | "api" | "auto" (auto = detect Ollama, fallback to API)
    """
    if choice == "api":
        # Force cloud API — clear any local overrides
        os.environ.pop("OPENAI_BASE_URL", None)
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key or api_key == "ollama":
            print("⚠️  OPENAI_API_KEY not set! Set it as an environment variable.")
        else:
            masked = api_key[:8] + "..." + api_key[-4:]
            print(f"☁️  LLM: OpenAI Cloud API")
            print(f"   Key:   {masked}")
        os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")
        print(f"   Model: {os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')}")
        return

    if choice == "local":
        force_local = True
    else:
        force_local = False

    ollama_path = shutil.which("ollama")

    if ollama_path and (force_local or choice == "auto"):
        print("✅ Ollama detected. Using Local LLM.")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 11434))
            sock.close()
            if result != 0:
                print("⏳ Starting Ollama server...")
                subprocess.Popen(["ollama", "serve"],
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                time.sleep(3)
        except Exception:
            pass
        os.environ["OPENAI_BASE_URL"] = "http://localhost:11434/v1"
        os.environ["OPENAI_MODEL"] = "llama3.1"
        os.environ["OPENAI_API_KEY"] = "ollama"
        print(f"✅ LLM: Local Ollama")
        print(f"   Model: {os.environ['OPENAI_MODEL']}")
        print(f"   URL:   {os.environ['OPENAI_BASE_URL']}")
    elif force_local:
        print("❌ Ollama not found! Install from https://ollama.ai")
        print("   Falling back to OpenAI Cloud API.")
        configure_llm_mode("api")
    else:
        # auto with no Ollama => cloud
        print("⚠️ Ollama not found.")
        configure_llm_mode("api")

# Deferred — will be called from __main__ after user selects LLM mode

#  CONFIG OPENAI / OBJETIVOS
# ==========================
# Use local LLM if configured, otherwise use default OpenAI
_base_url = os.environ.get("OPENAI_BASE_URL", getattr(Config.AI, 'OPENAI_BASE_URL', None))
_api_key = os.environ.get("OPENAI_API_KEY", getattr(Config.AI, 'OPENAI_API_KEY', None))
_model = os.environ.get("OPENAI_MODEL", getattr(Config.AI, 'OPENAI_MODEL', "gpt-4o-mini"))

client = OpenAI(api_key=_api_key, base_url=_base_url)

def reinit_llm_client():
    """Re-read env vars and rebuild the OpenAI client after user selects LLM mode."""
    global _base_url, _api_key, _model, client
    _base_url = os.environ.get("OPENAI_BASE_URL", getattr(Config.AI, 'OPENAI_BASE_URL', None))
    _api_key = os.environ.get("OPENAI_API_KEY", getattr(Config.AI, 'OPENAI_API_KEY', None))
    _model = os.environ.get("OPENAI_MODEL", getattr(Config.AI, 'OPENAI_MODEL', "gpt-4o-mini"))
    client = OpenAI(api_key=_api_key, base_url=_base_url)

# Navigation constants (from Config)
DISTANCE_TARGET = getattr(Config.Navigation, 'DISTANCE_TARGET', 0.3)
DIST_CORRECTION = getattr(Config.Navigation, 'DISTANCE_CORRECTION', 1.0)
YOLO_CONF = getattr(Config.AI, 'YOLO_CONFIDENCE', 0.5)

# Navigation speed safety mode (toggle with keybind) — thread-safe Event
_NAV_SAFE_MODE_EVT = threading.Event()   # .is_set() == safe mode ON

def get_nav_safe_mode() -> bool:
    return _NAV_SAFE_MODE_EVT.is_set()

def toggle_nav_safe_mode() -> bool:
    """Toggle safe mode and return the new state."""
    if _NAV_SAFE_MODE_EVT.is_set():
        _NAV_SAFE_MODE_EVT.clear()
    else:
        _NAV_SAFE_MODE_EVT.set()
    return _NAV_SAFE_MODE_EVT.is_set()

# ArUco marker constants
ARUCO_MARKER_SIZE = getattr(Config.Vision, 'ARUCO_MARKER_SIZE', 0.20)

# Detection constants
DETECTION_RADIUS_SCALE = getattr(Config.Navigation, 'DETECTION_RADIUS_SCALE', 2.0)
ROI_EXPANSION_SCALE = getattr(Config.Vision, 'ROI_EXPANSION_SCALE', 1.2)
MARKER_EXPIRE_TIME = getattr(Config.Navigation, 'MARKER_EXPIRE_TIME', 2.0)
SMOOTH_WINDOW_SIZE = getattr(Config.Vision, 'SMOOTH_WINDOW_SIZE', 5)

# Camera correction
GAMMA_CORRECTION = getattr(Config.Vision, 'GAMMA_CORRECTION', 1.2)

# Configuraciones por tipo de fuente — single canonical definition.
if hasattr(Config, 'Source') and hasattr(Config.Source, 'get_source_configs'):
    SOURCE_CONFIGS = Config.Source.get_source_configs()
elif hasattr(Config, 'Source') and hasattr(Config.Source, 'SOURCES'):
    SOURCE_CONFIGS = Config.Source.SOURCES
else:
    SOURCE_CONFIGS = {
        "default": {"calibration": "calibration/calINSPIRO.npz", "detection_interval": 5, "target_fps": 30, "control": "wifi"},
        "scrcpy":  {"calibration": "calibration/calINSPIRO.npz", "detection_interval": 5, "target_fps": 30, "control": "serial"},
        "smartview": {"calibration": "calibration/calINSPIRO.npz", "detection_interval": 3, "target_fps": 30, "control": "serial"},
        "phone_stream": {"calibration": "calibration/calINSPIRO.npz", "detection_interval": 2, "target_fps": 20, "port": 8080, "path": "/stream.mjpeg", "control": "serial"},
        "stream": {"calibration": "calibration/calINSPIRO.npz", "detection_interval": 1, "target_fps": 15, "url": f"http://{CamIP}/stream", "control": "wifi"},
    }

# ==========================
#  CONSOLA GUI
# ==========================
class ConsoleBuffer:
    def __init__(self, max_lines=None, max_history=None):
        if max_lines is None:
            max_lines = getattr(getattr(Config, 'UI', None), 'MAX_CONSOLE_LINES', 100)
        if max_history is None:
            max_history = getattr(getattr(Config, 'UI', None), 'MAX_COMMAND_HISTORY', 50)
        
        self.buffer = deque(maxlen=max_lines)
        self.current_input = ""
        self.command_history = deque(maxlen=max_history)
        self.history_index = -1
        self.lock = threading.Lock()
        self.cmd_queue = Queue()  # Thread-safe command queue for prompt_thread
        
    def add_output(self, text):
        with self.lock:
            self.buffer.extend(text.split('\n'))
        
    def get_visible_buffer(self):
        with self.lock:
            return list(self.buffer)
        
    def clear_input(self):
        with self.lock:
            self.current_input = ""
        
    def add_to_input(self, char):
        with self.lock:
            self.current_input += char
        
    def backspace(self):
        with self.lock:
            self.current_input = self.current_input[:-1]
    
    def get_input(self):
        with self.lock:
            return self.current_input
    
    def add_to_history(self, command):
        """Add command to history"""
        with self.lock:
            if command and (not self.command_history or self.command_history[-1] != command):
                self.command_history.append(command)
            self.history_index = -1
    
    def history_up(self):
        """Navigate up in command history"""
        with self.lock:
            if not self.command_history:
                return
            if self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                self.current_input = self.command_history[-(self.history_index + 1)]
    
    def history_down(self):
        """Navigate down in command history"""
        with self.lock:
            if self.history_index > 0:
                self.history_index -= 1
                self.current_input = self.command_history[-(self.history_index + 1)]
            elif self.history_index == 0:
                self.history_index = -1
                self.current_input = ""

    def submit_command(self, text):
        """Submit a command: display it, record in history, enqueue for prompt_thread."""
        self.add_output(f"> {text}")
        self.add_to_history(text)
        self.cmd_queue.put(text)
        self.clear_input()

# ==========================
#  UTIL
# ==========================
def compute_fov(fx: float, fy: float, width: int, height: int):
    """Calculate horizontal and vertical FoV in degrees."""
    fov_x = 2 * np.degrees(np.arctan(width / (2 * fx)))
    fov_y = 2 * np.degrees(np.arctan(height / (2 * fy)))
    return fov_x, fov_y

# ==========================
#  NUMBA JIT OPTIMIZATIONS
# ==========================
try:
    from numba import jit
    
    @jit(nopython=True, cache=True)
    def calculate_distance_fast(tvec_flat: npt.NDArray[np.float64]) -> float:
        """JIT-compiled distance calculation (10-100x faster)"""
        return np.sqrt(tvec_flat[0]**2 + tvec_flat[1]**2 + tvec_flat[2]**2)
    
    @jit(nopython=True, cache=True)
    def calculate_angles_fast(cx: float, cy: float, frame_w: float, frame_h: float, 
                             fov_x: float, fov_y: float) -> tuple[float, float]:
        """JIT-compiled angle calculation (10-100x faster)"""
        ax = ((cx - frame_w/2) / frame_w) * fov_x
        ay = ((frame_h/2 - cy) / frame_h) * fov_y
        return ax, ay
    
    NUMBA_AVAILABLE = True
    print("✅ Numba JIT habilitado - cálculos 10-100x más rápidos")
except ImportError:
    NUMBA_AVAILABLE = False
    print("⚠️ Numba no disponible - usando cálculos estándar")
    
    # Fallback to regular functions
    def calculate_distance_fast(tvec_flat):
        return float(np.linalg.norm(tvec_flat))
    
    def calculate_angles_fast(cx, cy, frame_w, frame_h, fov_x, fov_y):
        ax = ((cx - frame_w/2) / frame_w) * fov_x
        ay = ((frame_h/2 - cy) / frame_h) * fov_y
        return ax, ay

# ==========================
#  POSE-BASED DISTANCE ESTIMATION (Alternative to ArUco)
# ==========================

# Human body measurements (meters)
TORSO_AVG_WIDTH_M = 0.40   # Average shoulder width (40cm)
TORSO_AVG_HEIGHT_M = 0.50  # Average torso height (shoulder to hip)
HEAD_SHOULDER_M = 0.25     # Average nose-to-shoulder vertical distance (~25cm)
SHIN_LENGTH_M = 0.45       # Average shin length (knee to ankle)
INTER_EYE_M = 0.063        # Average inter-pupillary distance (~6.3cm)
FULL_HEIGHT_M = 1.70       # Average full person height for bbox fallback
FOCAL_PIX_DEFAULT = 640.0  # Default focal length in pixels (Lenovo LOQ 15 webcam @ 720p ~600-700px)
CONF_MIN_KPT = 0.3         # Minimum keypoint confidence (lowered for webcam quality)

# Distance smoothing
DIST_EMA_ALPHA = 0.35      # EMA blending factor (0 = all history, 1 = all current)

# Per-person adaptive calibration
CALIB_HISTORY_MIN = 8           # Min fused samples before learning a correction
CALIB_OUTLIER_THRESH = 0.50     # Max allowed deviation from median (50%) before rejecting an estimator

# Orientation detection: when frontal, shoulder_width / torso_height ≈ 0.75-0.85
# When sideways (90°), this ratio drops to ≈ 0.25-0.40
FRONTAL_RATIO_EXPECTED = 0.80  # shoulder_w / torso_h when facing camera
SIDEWAYS_RATIO_THRESHOLD = 0.50  # below this => mostly sideways

# COCO keypoint indices (used globally)
KPT_NOSE = 0
KPT_L_EYE, KPT_R_EYE = 1, 2
KPT_L_EAR, KPT_R_EAR = 3, 4
KPT_L_SH, KPT_R_SH = 5, 6       # shoulders
KPT_L_ELB, KPT_R_ELB = 7, 8     # elbows
KPT_L_WRI, KPT_R_WRI = 9, 10    # wrists
KPT_L_HP, KPT_R_HP = 11, 12     # hips
KPT_L_KN, KPT_R_KN = 13, 14     # knees
KPT_L_AN, KPT_R_AN = 15, 16     # ankles

def distance_between_kpts(p1, p2):
    """Calculate Euclidean distance between two keypoints"""
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def _kpt_visible(kpts, idx):
    """Check if a keypoint is visible (above confidence threshold)"""
    return idx < len(kpts) and kpts[idx][2] > CONF_MIN_KPT

# ==========================
#  GESTURE RECOGNITION (F1)
# ==========================
# Gesture types detected from pose keypoints
GESTURE_NONE = None
GESTURE_HAND_RAISED = 'hand_raised'       # One hand above head → "come here"
GESTURE_BOTH_HANDS_UP = 'both_hands_up'   # Both hands above head → "stop"
GESTURE_WAVE = 'wave'                      # Wrist oscillation → "follow me"

# Minimum frames a gesture must persist to be triggered (debounce)
GESTURE_MIN_FRAMES = 8
# Cooldown (seconds) between the same gesture triggering a command
GESTURE_COOLDOWN = 10.0
# Minimum keypoint confidence for wrist/elbow in gesture detection
GESTURE_KPT_CONF = 0.5

def detect_gesture(kpts, gesture_history: deque, bbox=None) -> Optional[str]:
    """Detect a gesture from pose keypoints.

    Args:
        kpts: (17, 3) keypoints  (x, y, confidence)
        gesture_history: deque(maxlen=10) of recent gesture strings (caller managed)
        bbox: (x1, y1, x2, y2) bounding box — used to reject stray keypoints
              from overlapping persons

    Returns:
        Gesture string if a stable gesture is detected, else None.
    """
    gesture = GESTURE_NONE

    has_nose = _kpt_visible(kpts, KPT_NOSE)
    has_l_wri = _kpt_visible(kpts, KPT_L_WRI)
    has_r_wri = _kpt_visible(kpts, KPT_R_WRI)
    has_l_sh = _kpt_visible(kpts, KPT_L_SH)
    has_r_sh = _kpt_visible(kpts, KPT_R_SH)

    if not (has_nose and (has_l_sh or has_r_sh)):
        gesture_history.append(GESTURE_NONE)
        return GESTURE_NONE

    nose_y = kpts[KPT_NOSE][1]

    # --- Bbox-based containment margin ---
    # Allow wrist to extend above the bbox (raised hand) but reject wrists
    # that are horizontally far outside the person's box (likely another person).
    if bbox is not None:
        bx1, by1, bx2, by2 = bbox
        bw = bx2 - bx1
        # Horizontal margin: 50% of bbox width on each side
        x_lo = bx1 - bw * 0.5
        x_hi = bx2 + bw * 0.5
    else:
        x_lo, x_hi = -1e9, 1e9

    # Compute minimum vertical margin: wrist must be at least this far
    # above the nose to count as "raised".  Uses the shoulder-to-nose
    # distance as a body-relative ruler (≈ head height).
    ref_sh_idx = KPT_L_SH if has_l_sh else KPT_R_SH
    sh_y = kpts[ref_sh_idx][1]
    head_height = abs(sh_y - nose_y)  # shoulder-to-nose in pixels
    # Require wrist to be at least 0.6× head_height ABOVE the nose
    min_raise = max(head_height * 0.6, 15)  # at least 15px to guard tiny detections

    def _wrist_valid(wrist_idx, shoulder_idx, elbow_idx):
        """Check that a wrist is significantly above the nose AND plausibly
        belongs to this person: it must be horizontally within the expanded
        bbox and connected through a visible arm chain."""
        # Require higher confidence for gesture wrists
        if wrist_idx >= len(kpts) or kpts[wrist_idx][2] < GESTURE_KPT_CONF:
            return False
        wx, wy = kpts[wrist_idx][0], kpts[wrist_idx][1]
        # Must be significantly above nose (not just 1-2 pixels from jitter)
        if wy >= nose_y - min_raise:
            return False
        # Horizontal containment: reject wrists far outside this person's box
        if wx < x_lo or wx > x_hi:
            return False
        # Arm chain: require at least the shoulder to be visible and on
        # the same side as the wrist (elbow is nice-to-have but optional)
        if not _kpt_visible(kpts, shoulder_idx):
            return False
        sx = kpts[shoulder_idx][0]
        # Shoulder must also be within the expanded bbox
        if sx < x_lo or sx > x_hi:
            return False
        # If elbow is visible, verify it's between shoulder and wrist vertically
        # (sanity: elbow shouldn't be below the shoulder when hand is raised)
        if _kpt_visible(kpts, elbow_idx):
            ey = kpts[elbow_idx][1]
            sy = kpts[shoulder_idx][1]
            # Elbow should be above or near shoulder level when hand is up
            if ey > sy + abs(sy - wy) * 0.5:
                return False
        return True

    l_above = _wrist_valid(KPT_L_WRI, KPT_L_SH, KPT_L_ELB)
    r_above = _wrist_valid(KPT_R_WRI, KPT_R_SH, KPT_R_ELB)

    if l_above and r_above:
        gesture = GESTURE_BOTH_HANDS_UP
    elif l_above or r_above:
        gesture = GESTURE_HAND_RAISED

    gesture_history.append(gesture)

    # Debounce: require GESTURE_MIN_FRAMES consecutive identical gestures
    if gesture and len(gesture_history) >= GESTURE_MIN_FRAMES:
        recent = list(gesture_history)[-GESTURE_MIN_FRAMES:]
        if all(g == gesture for g in recent):
            return gesture

    return GESTURE_NONE

# ==========================
#  OBSTACLE DETECTION CLASSES (F6)
# ==========================
# COCO class IDs for common obstacles (used by YOLO 80-class models)
OBSTACLE_CLASSES = [
    # Vehicles
    2, 3, 5, 7,   # car, motorcycle, bus, truck
    # Outdoor objects
    9, 10, 11, 12, 13,  # traffic light, fire hydrant, stop sign, parking meter, bench
    # Animals
    15, 16, 17, 18, 19, 20, 21, 22, 23,  # cat through giraffe
    # Furniture / indoor
    56, 57, 58, 59, 60,  # chair, couch, potted plant, bed, dining table
    # Electronics
    62, 63, 72,  # tv, laptop, refrigerator
    # Misc
    24, 25, 28, 39, 64,  # backpack, umbrella, suitcase, bottle, mouse
]
OBSTACLE_DETECT_INTERVAL = 5   # Run obstacle detection every N frames
OBSTACLE_CONFIDENCE = 0.40     # Lower threshold since we want safety-first

def estimate_body_orientation(kpts):
    """
    Estimate how much the person is facing the camera (0.0 = fully sideways, 1.0 = fully frontal).
    Uses the ratio of shoulder width to torso height — vertical measurements are
    rotation-invariant while horizontal ones compress with body rotation.
    
    Returns: (frontal_score 0..1, method_used str)
    """
    has_shoulders = _kpt_visible(kpts, KPT_L_SH) and _kpt_visible(kpts, KPT_R_SH)
    has_hips = _kpt_visible(kpts, KPT_L_HP) and _kpt_visible(kpts, KPT_R_HP)
    
    # Primary: shoulder width vs torso height ratio
    if has_shoulders and has_hips:
        shoulder_w = abs(kpts[KPT_L_SH][0] - kpts[KPT_R_SH][0])
        torso_h = max(kpts[KPT_L_HP][1], kpts[KPT_R_HP][1]) - min(kpts[KPT_L_SH][1], kpts[KPT_R_SH][1])
        if torso_h > 5:
            ratio = shoulder_w / torso_h
            # Map ratio to 0..1 frontal score
            # ratio ~0.80 = frontal (score=1.0), ratio ~0.25 = sideways (score=0.0)
            score = max(0.0, min(1.0, (ratio - 0.25) / (FRONTAL_RATIO_EXPECTED - 0.25)))
            return score, 'shoulder_torso_ratio'
    
    # Secondary: hip width vs torso height (hips rotate similarly)
    if has_hips and has_shoulders:
        hip_w = abs(kpts[KPT_L_HP][0] - kpts[KPT_R_HP][0])
        torso_h = max(kpts[KPT_L_HP][1], kpts[KPT_R_HP][1]) - min(kpts[KPT_L_SH][1], kpts[KPT_R_SH][1])
        if torso_h > 5:
            ratio = hip_w / torso_h
            score = max(0.0, min(1.0, (ratio - 0.15) / (0.55 - 0.15)))
            return score, 'hip_torso_ratio'
    
    # Tertiary: check ear visibility asymmetry (if one ear visible but not other → sideways)
    l_ear = _kpt_visible(kpts, KPT_L_EAR)
    r_ear = _kpt_visible(kpts, KPT_R_EAR)
    if l_ear != r_ear:
        return 0.3, 'ear_asymmetry'  # One ear hidden → likely sideways
    
    # Default: assume mostly frontal
    return 0.7, 'default'

# ---- Color name mapping for clothing description ----
_COLOR_NAMES = [
    ((0, 0, 0),       'black'),
    ((255, 255, 255), 'white'),
    ((128, 128, 128), 'gray'),
    ((200, 0, 0),     'red'),
    ((0, 150, 0),     'green'),
    ((0, 0, 200),     'blue'),
    ((200, 200, 0),   'yellow'),
    ((200, 100, 0),   'orange'),
    ((150, 0, 150),   'purple'),
    ((200, 150, 120), 'beige'),
    ((100, 60, 30),   'brown'),
    ((0, 200, 200),   'cyan'),
    ((255, 180, 200), 'pink'),
    ((0, 0, 80),      'navy'),
]

def _closest_color_name(bgr_pixel):
    """Map a BGR pixel to the nearest named color."""
    b, g, r = int(bgr_pixel[0]), int(bgr_pixel[1]), int(bgr_pixel[2])
    best_name = 'unknown'
    best_dist = float('inf')
    for (cr, cg, cb), name in _COLOR_NAMES:
        d = (r - cr)**2 + (g - cg)**2 + (b - cb)**2
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name

def extract_clothing_colors(frame, kpts, bbox):
    """
    Extract dominant upper-body (shirt) and lower-body (pants) color names
    from the person's bounding box using keypoint-guided regions.
    Very lightweight: samples a small patch and computes the mean color.
    Returns: (upper_color: str, lower_color: str)
    """
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    
    # Clamp to frame bounds
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    bw, bh = x2 - x1, y2 - y1
    if bw < 5 or bh < 5:
        return 'unknown', 'unknown'
    
    # Use keypoints if available for more precise regions
    has_sh = _kpt_visible(kpts, KPT_L_SH) and _kpt_visible(kpts, KPT_R_SH)
    has_hp = _kpt_visible(kpts, KPT_L_HP) and _kpt_visible(kpts, KPT_R_HP)
    
    if has_sh and has_hp:
        # Upper body: between shoulders and hips (torso/shirt region)
        sh_y = int(min(kpts[KPT_L_SH][1], kpts[KPT_R_SH][1]))
        hp_y = int(max(kpts[KPT_L_HP][1], kpts[KPT_R_HP][1]))
        # Inset horizontally by 20% to avoid background
        inset = int(bw * 0.2)
        upper_region = frame[max(0, sh_y):min(h, hp_y), x1 + inset:x2 - inset]
        # Lower body: from hips to bottom of bbox
        lower_region = frame[min(h, hp_y):y2, x1 + inset:x2 - inset]
    else:
        # Fallback: split bbox into upper 40% and lower 40%
        mid = y1 + bh // 2
        top_third = y1 + bh // 3
        bot_third = y1 + 2 * bh // 3
        inset = int(bw * 0.2)
        upper_region = frame[top_third:mid, x1 + inset:x2 - inset]
        lower_region = frame[mid:bot_third, x1 + inset:x2 - inset]
    
    upper_color = 'unknown'
    lower_color = 'unknown'
    
    if upper_region.size > 0 and upper_region.shape[0] > 2 and upper_region.shape[1] > 2:
        mean_bgr = upper_region.mean(axis=(0, 1))
        upper_color = _closest_color_name(mean_bgr)
    
    if lower_region.size > 0 and lower_region.shape[0] > 2 and lower_region.shape[1] > 2:
        mean_bgr = lower_region.mean(axis=(0, 1))
        lower_color = _closest_color_name(mean_bgr)
    
    return upper_color, lower_color

def _position_label(angle_x):
    """Convert X angle to a human-readable position label."""
    if angle_x < -15:
        return 'far left'
    elif angle_x < -5:
        return 'left'
    elif angle_x > 15:
        return 'far right'
    elif angle_x > 5:
        return 'right'
    else:
        return 'center'

def _estimate_posture(kpts):
    """Estimate posture from keypoints: standing, sitting, crouching, or unknown.
    Compares vertical ratios between head, hips, and lower body.
    Cost: ~0 (pure arithmetic on existing keypoint array)."""
    has_nose = _kpt_visible(kpts, KPT_NOSE)
    has_hips = _kpt_visible(kpts, KPT_L_HP) or _kpt_visible(kpts, KPT_R_HP)
    has_knees = _kpt_visible(kpts, KPT_L_KN) or _kpt_visible(kpts, KPT_R_KN)
    has_ankles = _kpt_visible(kpts, KPT_L_AN) or _kpt_visible(kpts, KPT_R_AN)
    
    if not (has_nose and has_hips):
        return 'unknown'
    
    nose_y = kpts[KPT_NOSE][1]
    hip_y = max(
        kpts[KPT_L_HP][1] if _kpt_visible(kpts, KPT_L_HP) else 0,
        kpts[KPT_R_HP][1] if _kpt_visible(kpts, KPT_R_HP) else 0
    )
    
    if has_ankles:
        ankle_y = max(
            kpts[KPT_L_AN][1] if _kpt_visible(kpts, KPT_L_AN) else 0,
            kpts[KPT_R_AN][1] if _kpt_visible(kpts, KPT_R_AN) else 0
        )
        total_h = ankle_y - nose_y
        upper_h = hip_y - nose_y
        if total_h > 20:
            ratio = upper_h / total_h
            # Standing: upper body is ~50-55% of total height
            # Sitting: upper body is ~70-90% (legs folded)
            if ratio < 0.62:
                return 'standing'
            elif ratio < 0.80:
                return 'sitting'
            else:
                return 'crouching'
    elif has_knees:
        knee_y = max(
            kpts[KPT_L_KN][1] if _kpt_visible(kpts, KPT_L_KN) else 0,
            kpts[KPT_R_KN][1] if _kpt_visible(kpts, KPT_R_KN) else 0
        )
        leg_segment = knee_y - hip_y
        upper_h = hip_y - nose_y
        if upper_h > 10 and leg_segment > 5:
            if leg_segment / upper_h > 0.3:
                return 'standing'
            else:
                return 'sitting'
    
    return 'unknown'

def _facing_label(frontal_score):
    """Convert frontal_score to a readable label."""
    if frontal_score >= 0.7:
        return 'facing camera'
    elif frontal_score >= 0.4:
        return 'angled'
    else:
        return 'facing away'

def _movement_label(current, previous):
    """Describe movement direction from current vs previous value.
    Returns label string. Threshold avoids noise."""
    if previous is None:
        return None
    delta = current - previous
    if abs(delta) < 0.05:  # noise threshold
        return 'stationary'
    return 'increasing' if delta > 0 else 'decreasing'

def _relative_height_label(bbox, frame_h):
    """Describe how much of the frame the person occupies."""
    if frame_h <= 0:
        return 'unknown'
    _, y1, _, y2 = bbox
    ratio = (y2 - y1) / frame_h
    if ratio > 0.75:
        return 'very close/tall'
    elif ratio > 0.5:
        return 'large'
    elif ratio > 0.25:
        return 'medium'
    else:
        return 'small/far'

def estimate_distance_from_pose(kpts, bbox, focal_pix=FOCAL_PIX_DEFAULT):
    """
    Estimate distance using pose keypoints with orientation-aware multi-method fusion.
    
    Instead of cascading (try shoulder, fallback to torso, etc.), this computes
    ALL available distance estimates and fuses them with weights that adapt to
    body orientation. Vertical measurements are weighted higher when the person 
    is sideways because they don't compress with rotation.
    
    kpts: np.array shape (17, 3) -> (x, y, conf)
    bbox: (x1, y1, x2, y2)
    Returns: (distance_meters, orientation_score, method_info, raw_estimates) or (None, None, None, [])
    """
    if focal_pix <= 0:
        return None, None, None, []
    
    # Step 1: Detect body orientation
    frontal_score, orient_method = estimate_body_orientation(kpts)
    
    # Step 2: Collect all available distance estimates with base weights
    estimates = []  # list of (distance, weight, method_name)
    
    # --- Shoulder width distance (HORIZONTAL - orientation-dependent) ---
    if _kpt_visible(kpts, KPT_L_SH) and _kpt_visible(kpts, KPT_R_SH):
        shoulder_width_pix = distance_between_kpts(
            (kpts[KPT_L_SH][0], kpts[KPT_L_SH][1]),
            (kpts[KPT_R_SH][0], kpts[KPT_R_SH][1])
        )
        if shoulder_width_pix > 10:
            # Compensate for rotation: divide by cos(rotation_angle)
            # frontal_score=1 → no compensation, frontal_score=0 → shoulder is compressed
            # The apparent width = real_width * cos(angle)
            # We estimate cos(angle) ≈ frontal_score (linearized)
            # So real_width ≈ apparent_width / max(frontal_score, 0.3)
            compensation = max(frontal_score, 0.30)  # clamp to avoid divide-by-near-zero
            corrected_shoulder_pix = shoulder_width_pix / compensation
            dist_shoulder = (TORSO_AVG_WIDTH_M * focal_pix) / corrected_shoulder_pix
            
            # Weight: high when frontal, low when sideways
            weight = 3.0 * frontal_score  # max weight 3.0 when frontal
            if weight > 0.3:
                estimates.append((dist_shoulder, weight, 'shoulders'))
    
    # --- Torso height distance (VERTICAL - rotation-invariant) ---
    if all(_kpt_visible(kpts, i) for i in [KPT_L_SH, KPT_R_SH, KPT_L_HP, KPT_R_HP]):
        y_shoulders = min(kpts[KPT_L_SH][1], kpts[KPT_R_SH][1])
        y_hips = max(kpts[KPT_L_HP][1], kpts[KPT_R_HP][1])
        torso_height_pix = y_hips - y_shoulders
        if torso_height_pix > 10:
            dist_torso = (TORSO_AVG_HEIGHT_M * focal_pix) / torso_height_pix
            # Weight: always good, even better when sideways (since horizontal is unreliable)
            weight = 2.5 + 1.5 * (1.0 - frontal_score)  # range 2.5 (frontal) to 4.0 (sideways)
            estimates.append((dist_torso, weight, 'torso_height'))
    
    # --- Head-to-shoulder distance (VERTICAL - rotation-invariant) ---
    has_nose = _kpt_visible(kpts, KPT_NOSE)
    has_any_shoulder = _kpt_visible(kpts, KPT_L_SH) or _kpt_visible(kpts, KPT_R_SH)
    if has_nose and has_any_shoulder:
        # Use the midpoint of visible shoulders
        if _kpt_visible(kpts, KPT_L_SH) and _kpt_visible(kpts, KPT_R_SH):
            sh_y = (kpts[KPT_L_SH][1] + kpts[KPT_R_SH][1]) / 2
        elif _kpt_visible(kpts, KPT_L_SH):
            sh_y = kpts[KPT_L_SH][1]
        else:
            sh_y = kpts[KPT_R_SH][1]
        head_sh_pix = abs(sh_y - kpts[KPT_NOSE][1])
        if head_sh_pix > 5:
            dist_head = (HEAD_SHOULDER_M * focal_pix) / head_sh_pix
            weight = 1.5  # decent auxiliary signal, always valid
            estimates.append((dist_head, weight, 'head_shoulder'))
    
    # --- Hip width distance (HORIZONTAL - orientation-dependent, like shoulders) ---
    if _kpt_visible(kpts, KPT_L_HP) and _kpt_visible(kpts, KPT_R_HP):
        hip_width_pix = distance_between_kpts(
            (kpts[KPT_L_HP][0], kpts[KPT_L_HP][1]),
            (kpts[KPT_R_HP][0], kpts[KPT_R_HP][1])
        )
        if hip_width_pix > 8:
            compensation = max(frontal_score, 0.30)
            corrected_hip_pix = hip_width_pix / compensation
            dist_hip = (0.35 * focal_pix) / corrected_hip_pix  # avg hip width ~35cm
            weight = 1.5 * frontal_score  # only trust when frontal
            if weight > 0.3:
                estimates.append((dist_hip, weight, 'hip_width'))
    
    # --- Knee-to-ankle (shin) distance (VERTICAL - rotation-invariant) ---
    l_kn_vis = _kpt_visible(kpts, KPT_L_KN)
    r_kn_vis = _kpt_visible(kpts, KPT_R_KN)
    l_an_vis = _kpt_visible(kpts, KPT_L_AN)
    r_an_vis = _kpt_visible(kpts, KPT_R_AN)
    shin_estimates = []
    if l_kn_vis and l_an_vis:
        shin_pix = abs(kpts[KPT_L_AN][1] - kpts[KPT_L_KN][1])
        if shin_pix > 8:
            shin_estimates.append(shin_pix)
    if r_kn_vis and r_an_vis:
        shin_pix = abs(kpts[KPT_R_AN][1] - kpts[KPT_R_KN][1])
        if shin_pix > 8:
            shin_estimates.append(shin_pix)
    if shin_estimates:
        avg_shin_pix = sum(shin_estimates) / len(shin_estimates)
        dist_shin = (SHIN_LENGTH_M * focal_pix) / avg_shin_pix
        weight = 2.0  # vertical, rotation-invariant, reliable when visible
        estimates.append((dist_shin, weight, 'shin'))

    # --- Inter-eye distance (close-range signal, < ~3 m) ---
    if _kpt_visible(kpts, KPT_L_EYE) and _kpt_visible(kpts, KPT_R_EYE):
        eye_dist_pix = distance_between_kpts(
            (kpts[KPT_L_EYE][0], kpts[KPT_L_EYE][1]),
            (kpts[KPT_R_EYE][0], kpts[KPT_R_EYE][1])
        )
        if eye_dist_pix > 5:
            # Compensate for rotation (eyes compress horizontally like shoulders)
            compensation = max(frontal_score, 0.40)
            corrected_eye_pix = eye_dist_pix / compensation
            dist_eye = (INTER_EYE_M * focal_pix) / corrected_eye_pix
            # Only trust at close range (< ~3 m) — at far distances eye separation
            # is just a few pixels and noise dominates
            if dist_eye < 3.5:
                weight = 2.5 * frontal_score  # very accurate when frontal + close
                if weight > 0.3:
                    estimates.append((dist_eye, weight, 'inter_eye'))

    # --- Bounding box height (always available, rotation-invariant but noisy) ---
    # Adapt reference height based on which body parts are actually visible
    x1, y1, x2, y2 = bbox
    bbox_height = y2 - y1
    if bbox_height > 10:
        # Determine what portion of the body the bbox covers
        has_ankles = _kpt_visible(kpts, KPT_L_AN) or _kpt_visible(kpts, KPT_R_AN)
        has_knees = _kpt_visible(kpts, KPT_L_KN) or _kpt_visible(kpts, KPT_R_KN)
        has_hips = _kpt_visible(kpts, KPT_L_HP) or _kpt_visible(kpts, KPT_R_HP)
        has_head = _kpt_visible(kpts, KPT_NOSE)
        
        if has_ankles and has_head:
            ref_height = FULL_HEIGHT_M              # 1.70m — full body visible
        elif has_knees and has_head:
            ref_height = FULL_HEIGHT_M * 0.75       # ~1.28m — head to knees
        elif has_hips and has_head:
            ref_height = FULL_HEIGHT_M * 0.55       # ~0.94m — head to hips (upper body)
        elif has_head:
            ref_height = FULL_HEIGHT_M * 0.35       # ~0.60m — head + shoulders only
        else:
            ref_height = FULL_HEIGHT_M              # fallback to full height
        
        dist_bbox = (ref_height * focal_pix) / bbox_height
        weight = 1.0  # lowest priority, always available
        estimates.append((dist_bbox, weight, 'bbox_height'))
    
    # Step 3: Outlier rejection + weighted fusion
    if not estimates:
        return None, None, None, []
    
    # If we have 3+ estimates, reject outliers before fusing.
    # An estimate is an outlier if it deviates > CALIB_OUTLIER_THRESH from the
    # weighted-median of all estimates.
    if len(estimates) >= 3:
        # Compute a rough weighted median (sort by distance, walk weights to 50%)
        sorted_est = sorted(estimates, key=lambda e: e[0])
        half_total = sum(w for _, w, _ in sorted_est) / 2
        cum = 0.0
        w_median = sorted_est[len(sorted_est) // 2][0]  # fallback
        for d, w, _ in sorted_est:
            cum += w
            if cum >= half_total:
                w_median = d
                break
        # Keep only estimates within CALIB_OUTLIER_THRESH of the weighted median
        filtered = [
            (d, w, m) for d, w, m in estimates
            if abs(d - w_median) / max(w_median, 0.01) <= CALIB_OUTLIER_THRESH
        ]
        if len(filtered) >= 2:
            estimates = filtered
    
    total_weight = sum(w for _, w, _ in estimates)
    fused_distance = sum(d * w for d, w, _ in estimates) / total_weight
    methods_used = '+'.join(f"{m}({w:.1f})" for _, w, m in estimates)
    
    return fused_distance, frontal_score, methods_used, estimates

def check_torso_visibility(kpts):
    """
    Check if torso is visible from keypoints (enhanced version from standing1.2)
    Returns: 'full', 'partial', or 'none'
    """
    torso_points = [KPT_L_SH, KPT_R_SH, KPT_L_HP, KPT_R_HP]
    upper_body_points = [KPT_NOSE, KPT_L_EYE, KPT_R_EYE, KPT_L_EAR, KPT_R_EAR,
                         KPT_L_SH, KPT_R_SH, KPT_L_ELB, KPT_R_ELB]

    visible_torso_points = sum(1 for i in torso_points if _kpt_visible(kpts, i))
    visible_upper_points = sum(1 for i in upper_body_points if _kpt_visible(kpts, i))

    shoulders_visible = _kpt_visible(kpts, KPT_L_SH) and _kpt_visible(kpts, KPT_R_SH)
    hips_visible = _kpt_visible(kpts, KPT_L_HP) and _kpt_visible(kpts, KPT_R_HP)

    if shoulders_visible and hips_visible:
        return 'full'
    elif visible_torso_points >= 2 and visible_upper_points >= 5:
        return 'partial'
    else:
        return 'none'

# ==========================
#  PROCESADOR VIDEO
# ==========================
class VideoProcessor:
    def __init__(self, source_type="default", detection_interval=5, expire_time=MARKER_EXPIRE_TIME, roi_scale=ROI_EXPANSION_SCALE, gamma=GAMMA_CORRECTION):
        # Configuración según el tipo de fuente
        self.show_video_info = True
        
        self.source_type = source_type
        config = SOURCE_CONFIGS.get(source_type, SOURCE_CONFIGS["default"])
        
        self.calibration_file = config["calibration"]
        self.detection_interval = config["detection_interval"]
        self.target_fps = config["target_fps"]

        # Camera calibration (lazy loaded)
        self.K = None
        self.D = None
        self.calibration_loaded = False
        
        self.manual_mode = False
        self.manual_mode_lock = threading.Lock()
        self.voice_enabled = True

        # 3D ArUco model
        s = ARUCO_MARKER_SIZE / 2
        self.obj_pts = np.array([
            [-s, s, 0], [s, s, 0], [s, -s, 0], [-s, -s, 0]
        ], dtype=np.float32)

        # Gamma correction (cached)
        self.gamma = gamma
        self._gamma_table_cache = None

        # YOLO model (lazy loaded on first frame)
        self.yolo = None
        self.object_classes = None
        self.use_yolo_tracking = True  # Use built-in tracking instead of MOSSE
        
        # Pose model for distance estimation (lazy loaded)
        self.pose_model = None
        self.pose_device = None  # Track which device pose model is on ('cuda' or 'cpu')
        self.use_pose_distance = getattr(getattr(Config, 'AI', None), 'USE_POSE_DISTANCE', True)
        self.use_aruco = getattr(getattr(Config, 'AI', None), 'USE_ARUCO_MARKERS', False)
        
        # Face recognition (ArcFace via ONNX Runtime)
        self.face_system = None    # LiveFaceRecognition instance
        self.face_recognition_enabled = False
        self.pending_enrollment = None  # {'person_id': str, 'name': str, 'ts': float}
        self._raw_frame = None          # Latest un-annotated frame for enrollment
        
        # Get focal length from calibration file
        # Store BOTH the calibration focal length and the resolution it was calibrated at
        self._cal_focal = None
        self._cal_width = None
        ai_config = getattr(Config, 'AI', None)
        config_dir = os.path.dirname(os.path.abspath(__file__))
        cal_full_path = os.path.join(config_dir, self.calibration_file)
        if ai_config and hasattr(ai_config, 'get_focal_length'):
            focal = ai_config.get_focal_length(calibration_file=cal_full_path)
            if focal is not None:
                self._cal_focal = focal
                # Also read the calibration resolution to enable proper scaling
                try:
                    cal_data = np.load(cal_full_path)
                    self._cal_width = int(cal_data.get('width', 1280))
                except Exception:
                    self._cal_width = 1280  # default calibration resolution
                self.focal_length_pix = focal
                print(f"[INFO] Loaded focal length from calibration: {self.focal_length_pix:.2f}px (cal res: {self._cal_width}px wide)")
            else:
                self.focal_length_pix = FOCAL_PIX_DEFAULT
                print(f"[INFO] Calibration not found, using default: {FOCAL_PIX_DEFAULT}px (will auto-estimate from frame)")
        else:
            self.focal_length_pix = FOCAL_PIX_DEFAULT
            print(f"[WARNING] Using default focal length: {FOCAL_PIX_DEFAULT} pixels")

        # ArUco detector (lazy — only init when ArUco mode is enabled)
        self.aruco_dict = None
        self.detector = None
        if self.use_aruco:
            self._init_aruco_detector()

        # Parameters
        self.roi_scale = roi_scale
        self.expire_time = expire_time

        # Calibration data
        self.frame_width = None
        self.frame_height = None
        self.fov_x = None
        self.fov_y = None

        # State
        self.guided_mode = False
        self.selected_id = None
        self.stop_event = threading.Event()  # Critical: control de threads

        # Data structures
        self.trackers = {}
        self.rois = {}
        self.history = OrderedDict()
        self.smooth = {}
        self.object_detections = {}
        self.pose_detections = []
        
        # For pose-based detection
        self.processed_frame = None
        self.lock = threading.Lock()
        
        # Face recognition results (person_id -> (name, confidence))
        self.face_identities = {}
        
        # F1: Gesture recognition (toggled by hotkey)
        self.gesture_mode = False
        self.gesture_histories = {}       # person_id -> deque(maxlen=10) of gesture strings
        self.gesture_cooldowns = {}       # person_id -> {gesture: last_trigger_time}
        self.gesture_active = {}          # person_id -> current gesture string or None
        self.gesture_nav_target = None    # person_id currently being navigated to via gesture
        self.cancel_nav_event = threading.Event()  # set by gesture BOTH_HANDS_UP to cancel navigation
        self._find_person_pending = False  # True when waiting for name input after hotkey 9
        self._find_person_choice = None   # person_id waiting for go/follow response
        
        # F4: TTS enabled flag (speaks navigation events)
        self.tts_enabled = TTS_AVAILABLE
        
        # F6: Obstacle awareness
        self.obstacle_detections = []     # [(class_name, bbox, confidence), ...]
        self._obstacle_frame_counter = 0  # frame counter for throttled detection
        
        # GUI
        self.console = ConsoleBuffer()       # System log (fast updates, detection info)
        self.cmd_console = ConsoleBuffer()   # Command console (user commands & responses)
        self.input_text = ""
        self.show_gui = True
        self.layout = {
            'video_width': 0.7,
            'console_width': 0.3,
            'input_height': 40
        }
        self.last_print_time = 0
        self._frame_gen = 0  # incremented each time processed_frame is updated
        
    def _get_gamma_table(self):
        """Lazy load and cache gamma correction table"""
        if self._gamma_table_cache is None:
            invG = 1.0 / self.gamma
            self._gamma_table_cache = np.array([(i/255.0)**invG * 255 for i in range(256)], dtype=np.uint8)
        return self._gamma_table_cache

    def undistort(self, frame):
        return cv2.undistort(frame, self.K, self.D, None, self.K)

    def _init_aruco_detector(self):
        """Initialize ArUco detector (called lazily only when ArUco mode is enabled)."""
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        params = cv2.aruco.DetectorParameters()
        params.minMarkerPerimeterRate = 0.02
        params.adaptiveThreshWinSizeMin = 3
        params.adaptiveThreshWinSizeMax = 23
        params.adaptiveThreshConstant = 7
        params.polygonalApproxAccuracyRate = 0.05
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_CONTOUR
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, params)

    def _prune_expired(self):
        """Remove expired markers and clean up resources"""
        now = time.time()
        expired = []
        for mid, d in list(self.history.items()):
            if now - d['last_seen'] > self.expire_time:
                expired.append(mid)
        
        if expired:
            with self.lock:
                for mid in expired:
                    # Clean up tracker
                    tracker = self.trackers.pop(mid, None)
                    if tracker:
                        del tracker  # Explicitly delete
                    
                    self.rois.pop(mid, None)
                    self.object_detections.pop(mid, None)
                    self.smooth.pop(mid, None)
                    self.history.pop(mid, None)

    def validate_corners(self, pts):
        lengths = [np.linalg.norm(pts[(i+1)%4] - pts[i]) for i in range(4)]
        if min(lengths) <= 0:
            return False
        area = cv2.contourArea(pts)
        tol = 0.2 if area > 50000 else 0.4
        return (max(lengths)/min(lengths)) < (1 + tol)

    def _expand_roi(self, cx, cy, w, h, fh, fw):
        ew, eh = w*self.roi_scale, h*self.roi_scale
        x0 = max(0, int(cx - ew/2))
        y0 = max(0, int(cy - eh/2))
        x1 = min(fw, int(cx + ew/2))
        y1 = min(fh, int(cy + eh/2))
        return (x0, y0, x1-x0, y1-y0)

    def _get_active_markers(self):
        now = time.time()
        return [mid for mid, d in self.history.items() if now - d['last_seen'] <= self.expire_time]

    def _print_detection_info(self):
        now = time.time()
            
        output_lines = []
        with self.lock:
            output_lines.append("\n" + "="*50)
            output_lines.append("HISTORIAL DE MARCADORES:")
            
            if not self.history:
                output_lines.append("No hay marcadores en el historial")
            else:
                # Pre-compute active set once (avoids re-scanning history per marker)
                active_set = set(self._get_active_markers())
                for mid, d in self.history.items():
                    status = "ACTIVO" if mid in active_set else "INACTIVO"
                    line = f"\nID {mid} [{status}] | Última distancia: {d['distance']:.2f}m \n Ángulo X: {d['angle_x']:+.1f}° | Ángulo Y: {d['angle_y']:+.1f}°"
                    objs = self.object_detections.get(mid, [])
                    if objs:
                        line += "\n   Objetos detectados:"
                        for obj in objs:
                            cls_name = self.object_classes[obj['class_id']]
                            line += f"\n   - {cls_name} (confianza: {obj['confidence']:.2f})"
                    output_lines.append(line)
            output_lines.append("="*50 + "\n")
        
        self.console.add_output('\n'.join(output_lines))
        self.last_print_time = now

    def process_frame(self, frame):
        self.frame_idx = getattr(self, 'frame_idx', 0) + 1
        
        # Auto-detect frame dimensions from actual camera frame
        h, w = frame.shape[:2]
        if self.frame_width is None or self.frame_height is None or self.frame_width != w or self.frame_height != h:
            self.frame_width = w
            self.frame_height = h
            # Recompute FOV with updated dimensions
            if self.K is not None:
                fx, fy = self.K[0,0], self.K[1,1]
                self.fov_x, self.fov_y = compute_fov(fx, fy, w, h)
            elif self.fov_x is None or self.fov_y is None:
                self.fov_x = 60.0
                self.fov_y = 45.0
            # Scale focal length to match actual frame resolution
            if self._cal_focal is not None and self._cal_width is not None and self._cal_width != w:
                # Calibration was at a different resolution — scale proportionally
                scale = w / self._cal_width
                self.focal_length_pix = self._cal_focal * scale
                print(f"[INFO] Scaled focal length: {self._cal_focal:.1f}px (cal@{self._cal_width}px) → {self.focal_length_pix:.1f}px (frame@{w}px)")
            elif self.focal_length_pix == FOCAL_PIX_DEFAULT:
                # No calibration available — approximate from resolution (typical webcam ~65° HFOV)
                self.focal_length_pix = w / (2 * np.tan(np.radians(32.5)))  # ~65° HFOV
                print(f"[INFO] Auto-estimated focal length: {self.focal_length_pix:.1f}px for {w}x{h}")
            if self.frame_idx == 1:
                print(f"[INFO] Frame dimensions: {w}x{h}, FOV: {self.fov_x:.1f}°x{self.fov_y:.1f}°")
        
        # Early return if no calibration (only needed for ArUco)
        # Early return only if ArUco is the SOLE detection mode and calibration is missing
        if self.use_aruco and not self.use_pose_distance and (self.K is None or self.D is None):
            return
        
        # Undistort and enhance (only if using ArUco)
        if self.use_aruco and self.K is not None:
            und = self.undistort(frame)
            lut = cv2.LUT(und, self._get_gamma_table())
        else:
            lut = frame  # Use raw frame for pose (faster)

        # Optional: ArUco detection (legacy mode)
        if self.use_aruco:
            # Reutilizar gray buffer si existe
            if not hasattr(self, '_gray_buffer') or self._gray_buffer.shape[:2] != lut.shape[:2]:
                self._gray_buffer = np.empty(lut.shape[:2], dtype=np.uint8)
            cv2.cvtColor(lut, cv2.COLOR_BGR2GRAY, dst=self._gray_buffer)
            corners, ids, _ = self.detector.detectMarkers(self._gray_buffer)
        else:
            corners, ids = None, None

        seen = set()
        if self.use_aruco and ids is not None:
            self._prune_expired()
            fh, fw = frame.shape[:2]

            for idx, mid in enumerate(ids.flatten()):
                pts = corners[idx][0].astype(np.float32)
                if not self.validate_corners(pts): continue

                cx = float(pts[:,0].mean())
                cy = float(pts[:,1].mean())

                # Use Numba-optimized angle calculation
                ax, ay = calculate_angles_fast(cx, cy, float(self.frame_width), 
                                              float(self.frame_height), self.fov_x, self.fov_y)

                _, rvec, tvec = cv2.solvePnP(self.obj_pts, pts.astype(np.float32), self.K, self.D)
                # Use Numba-optimized distance calculation
                d = calculate_distance_fast(tvec.flatten()) * DIST_CORRECTION

                seen.add(mid)
                buf = self.smooth.setdefault(mid, {
                    'd': deque(maxlen=SMOOTH_WINDOW_SIZE),
                    'ax': deque(maxlen=SMOOTH_WINDOW_SIZE),
                    'ay': deque(maxlen=SMOOTH_WINDOW_SIZE)
                })
                buf['d'].append(d)
                buf['ax'].append(ax)
                buf['ay'].append(ay)
                d_med = float(sorted(buf['d'])[len(buf['d']) // 2])
                ax_med = float(sorted(buf['ax'])[len(buf['ax']) // 2])
                ay_med = float(sorted(buf['ay'])[len(buf['ay']) // 2])

                old = self.history.get(mid,{})
                with self.lock:
                    self.history[mid] = {
                        'corners': pts.astype(int),
                        'distance': d_med,
                        'angle_x': ax_med,
                        'angle_y': ay_med,
                        'prev_distance': old.get('distance'),
                        'prev_angle_x': old.get('angle_x'),
                        'prev_angle_y': old.get('angle_y'),
                        'last_seen': time.time(),
                        'draw_box': True,
                        'last_detection_time': time.time()
                    }

                lengths = [np.linalg.norm(pts[(j+1)%4]-pts[j]) for j in range(4)]
                w_px = float(np.mean(lengths))
                roi = self._expand_roi(cx, cy, w_px, w_px, fh, fw)
                tr = cv2.legacy.TrackerMOSSE_create()
                if tr.init(frame, roi):
                    self.trackers[mid] = tr
                    self.rois[mid] = roi

        # Tracking (only for ArUco markers)
        if self.use_aruco:
            for mid, tr in list(self.trackers.items()):
                if mid in seen: continue
                ok, bbox = tr.update(frame)
                if not ok:
                    with self.lock:
                        self.trackers.pop(mid, None)
                        self.rois.pop(mid, None)
                    continue
                x,y,w_,h_ = map(int, bbox)
                quad = np.array([[x,y],[x+w_,y],[x+w_,y+h_],[x,y+h_]], np.int32)
                with self.lock:
                    if mid in self.history:
                        self.history[mid].update({
                            'corners': quad,
                            'last_seen': time.time(),
                            'draw_box': False
                        })
        
        # PRIMARY: Pose-based detection (main navigation method)
        if self.use_pose_distance:
            self._detect_with_pose(frame)
        
        # Object detection for active targets (works with both ArUco and pose)
        active = self._get_active_markers()
        if active and self.use_aruco:
            self._detect_objects(frame, active)
        else:
            with self.lock:
                self.object_detections.clear()

        # Throttled detection info (only rebuild string when needed — every 1s)
        now = time.time()
        if now - self.last_print_time >= 1.0 and not self.guided_mode:
            self._print_detection_info()
        self._render_output(frame)

    def _detect_objects(self, frame, active):
        # Lazy load YOLO on first detection
        if self.yolo is None:
            print("🔍 Cargando modelo YOLO (primera vez)...")
            model_name = getattr(getattr(Config, 'AI', None), 'YOLO_MODEL', 'yolo11n.pt')
            model_path = os.path.join(_SCRIPT_DIR, model_name) if not os.path.isabs(model_name) else model_name
            self.yolo = YOLO(model_path)
            self.object_classes = self.yolo.names
            print("✅ Modelo YOLO listo (YOLOv11 con ByteTrack)")
        
        DET_RAD = DETECTION_RADIUS_SCALE
        # Use YOLO tracking with ByteTrack (built-in, more reliable than MOSSE)
        yolo_device = 0 if self.pose_device == 'cuda' else 'cpu'
        try:
            results = self.yolo.track(frame, conf=YOLO_CONF, verbose=False, device=yolo_device, persist=True, classes=[0])
        except Exception:
            results = self.yolo.track(frame, conf=YOLO_CONF, verbose=False, device='cpu', persist=True, classes=[0])     

        dets = {}
        with self.lock:
            data_map = {m:self.history[m] for m in active}

        for mid, d in data_map.items():
            mpos = np.mean(d['corners'], axis=0)
            size = np.linalg.norm(d['corners'][0]-d['corners'][1])
            radius = size*DET_RAD
            found = []
            for r in results:
                for box in r.boxes:
                    x1,y1,x2,y2 = map(int, box.xyxy[0])
                    pos = np.array([(x1+x2)/2, (y1+y2)/2])
                    if np.linalg.norm(pos-mpos) < radius:
                        obj = {
                            'class_id': int(box.cls),
                            'confidence': float(box.conf),
                            'bbox': (x1,y1,x2,y2)
                        }
                        # Add tracking ID if available (ByteTrack)
                        if box.id is not None:
                            obj['track_id'] = int(box.id)
                        found.append(obj)
            dets[mid] = found

        with self.lock:
            self.object_detections = dets
    
    def _detect_with_pose(self, frame, active=None):
        """
        PRIMARY detection using pose estimation for distance.
        Uses ByteTrack for persistent person IDs across frames and
        orientation-aware multi-method distance fusion with temporal smoothing.
        """
        # Lazy load pose model
        if self.pose_model is None:
            print("🧍 Cargando modelo de pose (primera vez)...")
            pose_name = getattr(getattr(Config, 'AI', None), 'POSE_MODEL', 'yolov8s-pose.pt')
            pose_path = os.path.join(_SCRIPT_DIR, pose_name) if not os.path.isabs(pose_name) else pose_name
            try:
                self.pose_model = YOLO(pose_path)
                if _HAS_CUDA:
                    self.pose_model.to('cuda')
                    self.pose_device = 'cuda'
                    print("✅ Modelo de pose listo - MODO PRINCIPAL (GPU: ON, ByteTrack tracking)")
                else:
                    self.pose_model.to('cpu')
                    self.pose_device = 'cpu'
                    print("✅ Modelo de pose listo (CPU mode, ByteTrack tracking)")
            except Exception as e:
                print(f"\n⚠️ Pose model loading failed: {e}")
                print(f"   Torch: {torch.__version__}, CUDA: {_HAS_CUDA}")
                if _HAS_CUDA:
                    print("⚠️  GPU falló, cambiando a CPU...")
                    try:
                        self.pose_model = YOLO(pose_path)
                        self.pose_model.to('cpu')
                        self.pose_device = 'cpu'
                        print("✅ Modelo de pose listo (CPU fallback)")
                    except Exception as e2:
                        print(f"❌ Falló también en CPU: {e2}")
                        self.use_pose_distance = False
                        return
                else:
                    print(f"❌ No se pudo cargar el modelo de pose: {e}")
                    self.use_pose_distance = False
                    return
        
        try:
            # Use .track() instead of __call__() for persistent ByteTrack IDs
            inf_device = 0 if self.pose_device == 'cuda' else 'cpu'
            use_half = (self.pose_device == 'cuda')  # FP16 on GPU = ~2x faster
            results = self.pose_model.track(
                frame, conf=0.55, verbose=False, device=inf_device,
                persist=True, imgsz=640, half=use_half, classes=[0]
            )
        except Exception as e:
            if not hasattr(self, '_pose_error_count'):
                self._pose_error_count = 0
            self._pose_error_count += 1
            if self._pose_error_count <= 3:
                print(f"[ERROR] Pose inference failed (#{self._pose_error_count}): {e}")
                if self.pose_device == 'cuda':
                    print("[WARN] Switching pose model to CPU after GPU failure...")
                    try:
                        self.pose_model.to('cpu')
                        self.pose_device = 'cpu'
                        print("[INFO] Switched to CPU successfully. Will retry next frame.")
                    except Exception as e2:
                        print(f"[ERROR] CPU switch also failed: {e2}")
            return
        
        res = results[0]
        if res.boxes is None or res.keypoints is None:
            return
        
        # Batch GPU→CPU transfer (single sync point instead of 3-4 separate ones)
        _boxes_t = res.boxes.xyxy
        _kpts_xy_t = res.keypoints.xy
        _kpts_conf_t = res.keypoints.conf
        _track_ids_t = res.boxes.id
        # Move all to CPU in one batch
        boxes = _boxes_t.cpu().numpy()
        kpts_xy = _kpts_xy_t.cpu().numpy()
        kpts_conf = _kpts_conf_t.cpu().numpy() if _kpts_conf_t is not None else np.ones(kpts_xy.shape[:2])
        track_ids = _track_ids_t.cpu().numpy().astype(int) if _track_ids_t is not None else None
        
        # Build full keypoints array once (xy + conf) instead of per-person concatenate
        all_kpts = np.concatenate([kpts_xy, kpts_conf.reshape(kpts_conf.shape[0], -1, 1)], axis=2)
        
        # Keep a raw (un-annotated) frame copy for face enrollment (thread-safe)
        # Only copy when face recognition is enabled (saves ~3-5ms/frame otherwise)
        if self.face_recognition_enabled:
            raw_copy = frame.copy()
            with self.lock:
                self._raw_frame = raw_copy
        
        seen_persons = set()
        
        for i in range(boxes.shape[0]):
            box = boxes[i]
            kpts = all_kpts[i]
            
            # Determine persistent person ID from ByteTrack, or fall back to index
            if track_ids is not None and i < len(track_ids):
                person_id = f"person_{track_ids[i]}"
            else:
                person_id = f"person_{i+1}"
            
            # Estimate distance with orientation-aware fusion
            result = estimate_distance_from_pose(kpts, box, self.focal_length_pix)
            distance, frontal_score, method_info, result_estimates = result
            
            # estimate_distance_from_pose already includes bbox_height internally;
            # if it still returned None, all estimators failed (very small detections).
            # Skip distance for this person rather than duplicating logic here.

            # Apply distance correction factor
            if distance is not None:
                distance = distance * DIST_CORRECTION
            
            torso_state = check_torso_visibility(kpts)
            
            if distance is not None:
                x1, y1, x2, y2 = box.astype(int)
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                angle_x, angle_y = calculate_angles_fast(
                    float(cx), float(cy), 
                    float(self.frame_width), float(self.frame_height),
                    self.fov_x, self.fov_y
                )
                
                seen_persons.add(person_id)
                
                # --- Temporal smoothing: EMA + median hybrid ---
                # Median rejects spikes; EMA gives recency bias for moving targets.
                buf = self.smooth.setdefault(person_id, {
                    'd': deque(maxlen=SMOOTH_WINDOW_SIZE),
                    'ax': deque(maxlen=SMOOTH_WINDOW_SIZE),
                    'ay': deque(maxlen=SMOOTH_WINDOW_SIZE),
                    'd_ema': None, 'ax_ema': None, 'ay_ema': None,
                })
                buf['d'].append(distance)
                buf['ax'].append(angle_x)
                buf['ay'].append(angle_y)
                # Fast median for small deques
                d_med = float(sorted(buf['d'])[len(buf['d']) // 2])
                ax_med = float(sorted(buf['ax'])[len(buf['ax']) // 2])
                ay_med = float(sorted(buf['ay'])[len(buf['ay']) // 2])
                # Blend: EMA on the median (best of both worlds)
                a = DIST_EMA_ALPHA
                if buf['d_ema'] is None:
                    buf['d_ema'], buf['ax_ema'], buf['ay_ema'] = d_med, ax_med, ay_med
                else:
                    buf['d_ema'] = a * d_med + (1 - a) * buf['d_ema']
                    buf['ax_ema'] = a * ax_med + (1 - a) * buf['ax_ema']
                    buf['ay_ema'] = a * ay_med + (1 - a) * buf['ay_ema']
                d_smooth = buf['d_ema']
                ax_smooth = buf['ax_ema']
                ay_smooth = buf['ay_ema']

                # --- Per-person adaptive calibration ---
                # Track how vertical (reliable) estimators compare to the fused result.
                # After enough samples, learn a per-person correction factor.
                calib = self.smooth[person_id].setdefault('_calib', {
                    'vert_dists': deque(maxlen=10),
                    'fused_dists': deque(maxlen=10),
                    'correction': 1.0,
                })
                # Collect vertical-only estimate for this frame (torso_height + shin)
                vert_est = [d for d, _w, m in result_estimates
                            if m in ('torso_height', 'shin', 'head_shoulder')]
                if vert_est and distance is not None:
                    avg_vert = sum(vert_est) / len(vert_est)
                    calib['vert_dists'].append(avg_vert)
                    calib['fused_dists'].append(distance)
                    if len(calib['fused_dists']) >= CALIB_HISTORY_MIN:
                        med_vert = float(sorted(calib['vert_dists'])[len(calib['vert_dists']) // 2])
                        med_fused = float(sorted(calib['fused_dists'])[len(calib['fused_dists']) // 2])
                        if med_fused > 0.05:
                            # Blend toward vertical-estimator truth slowly
                            raw_corr = med_vert / med_fused
                            # Clamp correction to sensible range (0.7 .. 1.4)
                            raw_corr = max(0.7, min(1.4, raw_corr))
                            calib['correction'] = 0.9 * calib['correction'] + 0.1 * raw_corr
                d_smooth *= calib['correction']
                
                # Store in history (navigation compatibility)
                old = self.history.get(person_id, {})
                corners = np.array([
                    [x1, y1], [x2, y1], [x2, y2], [x1, y2]
                ], dtype=np.int32)
                
                # Extract clothing colors (lightweight — ~0.1ms per person)
                try:
                    upper_color, lower_color = extract_clothing_colors(frame, kpts, (x1, y1, x2, y2))
                except Exception:
                    upper_color, lower_color = 'unknown', 'unknown'
                
                with self.lock:
                    self.history[person_id] = {
                        'corners': corners,
                        'distance': d_smooth,
                        'angle_x': ax_smooth,
                        'angle_y': ay_smooth,
                        'prev_distance': old.get('distance'),
                        'prev_angle_x': old.get('angle_x'),
                        'prev_angle_y': old.get('angle_y'),
                        'last_seen': time.time(),
                        'draw_box': True,
                        'last_detection_time': time.time(),
                        'type': 'person',
                        'torso_state': torso_state,
                        'keypoints': kpts,
                        'bbox': (x1, y1, x2, y2),
                        'frontal_score': frontal_score,
                        'distance_method': method_info,
                        'distance_raw': distance,
                        'upper_color': upper_color,
                        'lower_color': lower_color,
                        'position_label': _position_label(ax_smooth),
                    }
        
        # --- Clean up expired persons ---
        with self.lock:
            for pid in list(self.history.keys()):
                if pid.startswith('person_') and pid not in seen_persons:
                    if time.time() - self.history[pid].get('last_seen', 0) > self.expire_time:
                        del self.history[pid]
                        self.face_identities.pop(pid, None)
                        self.smooth.pop(pid, None)
                        self.gesture_histories.pop(pid, None)
                        self.gesture_cooldowns.pop(pid, None)
                        self.gesture_active.pop(pid, None)
        
        # --- F1: Gesture recognition (when enabled) ---
        if self.gesture_mode:
            self._process_gestures(seen_persons)
        
        # Face recognition on detected persons (uses keypoints — zero extra detection cost)
        if self.face_recognition_enabled and self.face_system:
            self._recognize_faces(frame, seen_persons)
        
        # --- F6: Obstacle detection (throttled) ---
        self._obstacle_frame_counter += 1
        if self._obstacle_frame_counter >= OBSTACLE_DETECT_INTERVAL:
            self._obstacle_frame_counter = 0
            self._detect_obstacles(frame)
    
    def _process_gestures(self, seen_persons):
        """F1: Detect gestures from keypoints and trigger actions.

        HAND_RAISED behaviour:
        - One-shot trigger: starts navigation to the calling person
        - Navigation persists even after the hand is lowered
        - Stops automatically at DISTANCE_TARGET (approach mode, no follow)
        - Only cancelled by BOTH_HANDS_UP from any visible person
        """
        now = time.time()

        # Clear gesture_nav_target when navigation has ended
        if self.gesture_nav_target and not self.guided_mode:
            self.gesture_nav_target = None

        for pid in seen_persons:
            data = self.history.get(pid)
            if not data or 'keypoints' not in data:
                continue
            kpts = data['keypoints']

            # Get or create gesture history for this person
            if pid not in self.gesture_histories:
                self.gesture_histories[pid] = deque(maxlen=10)

            gesture = detect_gesture(kpts, self.gesture_histories[pid],
                                     bbox=data.get('bbox'))
            self.gesture_active[pid] = gesture

            # --- BOTH_HANDS_UP: always processed (cancels gesture nav) ---
            if gesture == GESTURE_BOTH_HANDS_UP:
                cooldowns = self.gesture_cooldowns.setdefault(pid, {})
                last_trigger = cooldowns.get(gesture, 0)
                if now - last_trigger < GESTURE_COOLDOWN:
                    continue
                cooldowns[gesture] = now

                name_label = self.face_identities[pid][0] if pid in self.face_identities else pid
                self.cmd_console.add_output(f"🙌 {name_label}: BOTH HANDS UP → Stop/Emergency")
                if self.tts_enabled:
                    tts_speak(f"{name_label} signals stop")
                if self.guided_mode:
                    self.gesture_nav_target = None
                    self.cancel_nav_event.set()
                    self.cmd_console.submit_command(Config.Keybinds.KEY_CANCEL_NAV)
                continue

            # --- HAND_RAISED: one-shot persistent navigation trigger ---
            if gesture == GESTURE_HAND_RAISED:
                # Skip if we're already navigating to someone via gesture
                if self.gesture_nav_target and self.guided_mode:
                    continue

                cooldowns = self.gesture_cooldowns.setdefault(pid, {})
                last_trigger = cooldowns.get(gesture, 0)
                if now - last_trigger < GESTURE_COOLDOWN:
                    continue
                cooldowns[gesture] = now

                person_num = pid.split('_')[1]
                name_label = self.face_identities[pid][0] if pid in self.face_identities else pid
                self.cmd_console.add_output(f"✋ {name_label}: HAND RAISED → Navigating to them")
                if self.tts_enabled:
                    tts_speak(f"{name_label} is calling")

                # Mark as gesture-initiated navigation (persists after hand lowered)
                self.gesture_nav_target = pid
                self.cmd_console.submit_command(f"go to person {person_num}")
    
    def _detect_obstacles(self, frame):
        """F6: Run YOLO obstacle detection for non-person objects."""
        if self.yolo is None:
            # Lazy load YOLO model
            model_name = getattr(getattr(Config, 'AI', None), 'YOLO_MODEL', 'yolo11n.pt')
            model_path = os.path.join(_SCRIPT_DIR, model_name) if not os.path.isabs(model_name) else model_name
            try:
                self.yolo = YOLO(model_path)
                self.object_classes = self.yolo.names
            except Exception as e:
                print(f"[F6] YOLO load failed: {e}")
                return
        
        yolo_device = 0 if self.pose_device == 'cuda' else 'cpu'
        try:
            results = self.yolo(frame, conf=OBSTACLE_CONFIDENCE, verbose=False,
                                device=yolo_device, classes=OBSTACLE_CLASSES)
        except Exception:
            try:
                results = self.yolo(frame, conf=OBSTACLE_CONFIDENCE, verbose=False,
                                    device='cpu', classes=OBSTACLE_CLASSES)
            except Exception:
                return
        
        obstacles = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                cls_id = int(box.cls.cpu())
                conf = float(box.conf.cpu())
                cls_name = self.object_classes.get(cls_id, f"obj_{cls_id}")
                obstacles.append((cls_name, (x1, y1, x2, y2), conf))
        
        with self.lock:
            self.obstacle_detections = obstacles
    
    def _recognize_faces(self, frame, person_ids):
        """Recognise faces using pose keypoints + ArcFace embeddings."""
        for person_id in person_ids:
            data = self.history.get(person_id)
            if not data:
                continue
            kpts = data.get('keypoints')
            if kpts is None:
                continue
            try:
                name, sim = self.face_system.recognize_person(frame, kpts, person_id)
                if name:
                    with self.lock:
                        self.face_identities[person_id] = (name, sim)
            except Exception:
                pass  # don't let face rec crash detection

    def _render_output(self, frame):
        # Draw directly on the frame — no copy needed (saves ~2ms memcpy per frame)
        out = frame
        h, w = out.shape[:2]
        LT = cv2.LINE_8  # Fast aliased lines (LINE_AA is ~3x slower)
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # --- Crosshair ---
        cx_f, cy_f = w >> 1, h >> 1
        cv2.line(out, (cx_f - 20, cy_f), (cx_f + 20, cy_f), (100, 100, 255), 1, LT)
        cv2.line(out, (cx_f, cy_f - 20), (cx_f, cy_f + 20), (100, 100, 255), 1, LT)
        
        active = self._get_active_markers()
        
        # --- Compact HUD overlay (no blending — opaque dark rect) ---
        if self.show_video_info and active:
            ty = 24
            cv2.rectangle(out, (4, 4), (340, 10 + len(active) * 22 + 16), (15, 15, 15), -1)
            cv2.putText(out, "TRACKING", (10, ty), font, 0.55, (0, 200, 255), 1, LT)
            ty += 22
            for mid in active:
                d = self.history[mid]
                is_person = isinstance(mid, str) and mid.startswith('person_')
                if is_person:
                    pnum = mid.split('_')[1]
                    cv2.putText(out, f"P{pnum} {d['distance']:.1f}m X:{d['angle_x']:+.0f} Y:{d['angle_y']:+.0f}", (10, ty), font, 0.50, (220, 220, 220), 1, LT)
                else:
                    cv2.putText(out, f"ID{mid} {d['distance']:.1f}m", (10, ty), font, 0.50, (220, 220, 220), 1, LT)
                ty += 22

        # --- Skeleton connections (cached once) ---
        if not hasattr(self, '_skeleton_connections'):
            self._skeleton_connections = [
                (KPT_L_SH, KPT_R_SH), (KPT_L_HP, KPT_R_HP),
                (KPT_L_SH, KPT_L_HP), (KPT_R_SH, KPT_R_HP),
                (KPT_L_SH, KPT_L_ELB), (KPT_L_ELB, KPT_L_WRI),
                (KPT_R_SH, KPT_R_ELB), (KPT_R_ELB, KPT_R_WRI),
                (KPT_L_HP, KPT_L_KN), (KPT_L_KN, KPT_L_AN),
                (KPT_R_HP, KPT_R_KN), (KPT_R_KN, KPT_R_AN),
                (KPT_NOSE, KPT_L_EYE), (KPT_NOSE, KPT_R_EYE),
                (KPT_L_EYE, KPT_L_EAR), (KPT_R_EYE, KPT_R_EAR),
            ]

        # --- Render each detection ---
        for mid in active:
            d = self.history[mid]
            is_person = isinstance(mid, str) and mid.startswith('person_')
            
            if is_person:
                x1, y1, x2, y2 = d.get('bbox', (0, 0, 0, 0))
                distance = d.get('distance', 0)
                
                # Color by distance
                if distance < 1.0:
                    accent = (0, 140, 255)
                elif distance < 2.5:
                    accent = (255, 200, 0)
                else:
                    accent = (255, 120, 50)
                
                if d.get('torso_state') == 'none':
                    accent = (accent[0] >> 1, accent[1] >> 1, accent[2] >> 1)
                
                # Simple rectangle (1 call vs 8 corner lines)
                cv2.rectangle(out, (x1, y1), (x2, y2), accent, 2, LT)
                
                # Label above bbox — large, high-contrast, easy to read
                person_num = mid.split('_')[1]
                label = f"P{person_num}"
                if mid in self.face_identities:
                    name, confidence = self.face_identities[mid]
                    label = f"{name} {confidence:.0%}"
                    accent = (255, 0, 220)
                
                full_label = f"{label}  {distance:.1f}m"
                # Use getTextSize for pixel-perfect background sizing
                (tw, th), baseline = cv2.getTextSize(full_label, font, 0.65, 2)
                ly = max(th + 10, y1 - 8)
                pad = 6
                cv2.rectangle(out, (x1 - 1, ly - th - pad), (x1 + tw + pad * 2, ly + pad), accent, -1)
                cv2.putText(out, full_label, (x1 + pad, ly), font, 0.65, (255, 255, 255), 2, LT)
                
                # F1: Gesture badge below bbox
                if self.gesture_mode:
                    gesture = self.gesture_active.get(mid)
                    is_gesture_target = (self.gesture_nav_target == mid and self.guided_mode)
                    if gesture or is_gesture_target:
                        if is_gesture_target and not gesture:
                            # Hand lowered but still navigating to them
                            g_label = '>> NAVIGATING'
                            g_color = (0, 200, 0)  # Green
                        else:
                            gesture_labels = {
                                GESTURE_HAND_RAISED: '✋ HAND RAISED',
                                GESTURE_BOTH_HANDS_UP: '🙌 STOP',
                                GESTURE_WAVE: '👋 WAVE',
                            }
                            g_label = gesture_labels.get(gesture, gesture)
                            g_color = (0, 255, 255)  # Cyan
                        cv2.putText(out, g_label, (x1, y2 + 20), font, 0.55, g_color, 2, LT)
                
                # Skeleton — single thin line per connection, no glow
                if 'keypoints' in d:
                    kpts = d['keypoints']
                    pts_cache = {}
                    # Expand bbox by 30% to allow slight overshoot but
                    # reject garbage coords (e.g. 0,0) that cause lines
                    # flying off to corners
                    bw, bh = x2 - x1, y2 - y1
                    margin_x, margin_y = int(bw * 0.3), int(bh * 0.3)
                    kx_lo, kx_hi = x1 - margin_x, x2 + margin_x
                    ky_lo, ky_hi = y1 - margin_y, y2 + margin_y
                    for idx in range(min(17, len(kpts))):
                        if kpts[idx][2] > CONF_MIN_KPT:
                            kx, ky = int(kpts[idx][0]), int(kpts[idx][1])
                            if kx_lo <= kx <= kx_hi and ky_lo <= ky <= ky_hi:
                                pts_cache[idx] = (kx, ky)
                    
                    for a, b in self._skeleton_connections:
                        if a in pts_cache and b in pts_cache:
                            cv2.line(out, pts_cache[a], pts_cache[b], accent, 1, LT)
                    
                    # Single small dot per keypoint
                    for pt in pts_cache.values():
                        cv2.circle(out, pt, 2, accent, -1, LT)
            else:
                # ArUco marker
                if d['draw_box']:
                    cv2.polylines(out, [d['corners']], True, (0, 255, 120), 2, LT)
                    cv2.putText(out, f'ID:{mid}', tuple(d['corners'][0]), font, 0.6, (0, 255, 120), 1, LT)
            
            # Object detections
            if mid in self.object_detections:
                for obj in self.object_detections[mid]:
                    ox1, oy1, ox2, oy2 = obj['bbox']
                    cv2.rectangle(out, (ox1, oy1), (ox2, oy2), (255, 80, 80), 1, LT)
                    if self.show_video_info:
                        lbl = f"{self.object_classes[obj['class_id']]} {obj['confidence']:.0%}"
                        cv2.putText(out, lbl, (ox1, oy1 - 6), font, 0.40, (255, 80, 80), 1, LT)

        # --- F6: Render obstacle detections ---
        with self.lock:
            obstacles = list(self.obstacle_detections)
        if obstacles:
            for cls_name, (ox1, oy1, ox2, oy2), conf in obstacles:
                cv2.rectangle(out, (ox1, oy1), (ox2, oy2), (0, 0, 255), 1, LT)
                cv2.putText(out, f"! {cls_name} {conf:.0%}", (ox1, oy1 - 6), font, 0.40, (0, 0, 255), 1, LT)
        
        # --- F1: Gesture mode indicator ---
        if self.gesture_mode:
            cv2.putText(out, "GESTURE MODE ON", (w - 220, 30), font, 0.55, (0, 255, 255), 2, LT)

        self.processed_frame = out
        self._frame_gen += 1

    def _render_gui(self, frame):
        if not self.show_gui:
            return frame

        LT = cv2.LINE_8
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Pre-allocate all arrays once (1280x720 for speed — was 1920x1080)
        if not hasattr(self, '_gui_buffers'):
            total_w = 1280
            total_h = 720
            console_w = int(total_w * self.layout['console_width'])
            video_w = total_w - console_w
            status_h = 28
            input_h = min(self.layout['input_height'], 32)
            video_h = total_h - input_h - status_h
            
            self._gui_buffers = {
                'canvas': np.zeros((total_h, total_w, 3), dtype=np.uint8),
            }
            self._gui_dims = {
                'total_w': total_w, 'total_h': total_h,
                'console_w': console_w, 'video_w': video_w,
                'input_h': input_h, 'video_h': video_h,
                'status_h': status_h,
            }
        
        dims = self._gui_dims
        total_w = dims['total_w']
        console_w = dims['console_w']
        video_w = dims['video_w']
        input_h = dims['input_h']
        video_h = dims['video_h']
        status_h = dims['status_h']
        canvas = self._gui_buffers['canvas']

        # Resize frame maintaining aspect ratio
        h, w = frame.shape[:2]
        cache_key = (h, w)
        if not hasattr(self, '_resize_cache') or self._resize_cache['key'] != cache_key:
            aspect_ratio = w / h
            if aspect_ratio > video_w / video_h:
                new_w = video_w
                new_h = int(new_w / aspect_ratio)
            else:
                new_h = video_h
                new_w = int(new_h * aspect_ratio)
            x_offset = (video_w - new_w) // 2
            y_offset = (video_h - new_h) // 2
            self._resize_cache = {
                'key': cache_key,
                'new_w': new_w, 'new_h': new_h,
                'x_offset': x_offset, 'y_offset': y_offset
            }
        
        cache = self._resize_cache
        resized_frame = cv2.resize(frame, (cache['new_w'], cache['new_h']), interpolation=cv2.INTER_LINEAR)

        # Video area — fill dark then place frame
        vy1 = status_h
        vy2 = status_h + video_h
        canvas[vy1:vy2, 0:video_w] = (18, 18, 22)
        fy1 = vy1 + cache['y_offset']
        fx1 = cache['x_offset']
        canvas[fy1:fy1 + cache['new_h'], fx1:fx1 + cache['new_w']] = resized_frame

        # Console area — split into system log (top 1/4) and command console (bottom 3/4)
        cx1 = video_w
        console_h = vy2 - vy1
        syslog_h = console_h // 4
        cmdcon_h = console_h - syslog_h
        
        syslog_y1 = vy1
        syslog_y2 = vy1 + syslog_h
        cmdcon_y1 = syslog_y2
        cmdcon_y2 = vy2
        
        self._draw_system_log(canvas[syslog_y1:syslog_y2, cx1:total_w])
        self._draw_cmd_console(canvas[cmdcon_y1:cmdcon_y2, cx1:total_w])

        # Input bar — draw directly on canvas
        iy1 = vy2
        iy2 = iy1 + input_h
        self._draw_input(canvas[iy1:iy2, :])

        # Status bar — draw directly on canvas
        self._draw_status_bar(canvas[0:status_h, :])

        return canvas

    def _draw_status_bar(self, area):
        """Flat dark status bar — no gradient."""
        h, w = area.shape[:2]
        area[:] = (30, 30, 35)
        LT = cv2.LINE_8
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        cv2.putText(area, "SIGO", (8, h - 7), font, 0.50, (0, 200, 255), 1, LT)
        
        # Center: Mode indicator
        if self.guided_mode:
            mode_text, mode_color = "NAVIGATING", (0, 255, 120)
        elif hasattr(self, 'manual_mode') and self.manual_mode:
            mode_text, mode_color = "MANUAL", (0, 180, 255)
        else:
            mode_text, mode_color = "STANDBY", (100, 100, 110)
        mx = (w - len(mode_text) * 10) // 2
        cv2.putText(area, mode_text, (mx, h - 7), font, 0.50, mode_color, 1, LT)
        
        # Right: targets + device
        active = self._get_active_markers()
        n_persons = sum(1 for m in active if isinstance(m, str) and m.startswith('person_'))
        device_str = 'GPU' if getattr(self, 'pose_device', '') == 'cuda' else 'CPU'
        safe_txt = "SAFE" if get_nav_safe_mode() else "NORMAL"
        right_text = f"{n_persons}T | {device_str} | {safe_txt}"
        cv2.putText(area, right_text, (w - len(right_text) * 8 - 8, h - 7), font, 0.40, (180, 180, 190), 1, LT)

    def _draw_system_log(self, area):
        """Top panel: fast-scrolling system log (detection info, nav telemetry, debug)"""
        h, w = area.shape[:2]
        area[:] = (20, 20, 24)
        LT = cv2.LINE_8
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Header
        cv2.putText(area, "SYSTEM LOG", (6, 14), font, 0.34, (80, 80, 90), 1, LT)
        
        # Separator line at bottom
        cv2.line(area, (0, h - 1), (w, h - 1), (50, 50, 60), 1)
        
        # Compute layout params
        lh = max(10, int(12 * (h / 180)))
        font_scale = max(0.24, 0.30 * (h / 180))
        max_lines = max(1, (h - 20) // max(1, lh))
        
        visible_lines = self.console.get_visible_buffer()[-max_lines:]
        
        y = 18 + lh
        for line in visible_lines:
            cv2.putText(area, line[:80], (6, y), font, font_scale, (110, 110, 118), 1, LT)
            y += lh

    def _draw_cmd_console(self, area):
        """Bottom panel: clean command console (user commands & responses only)"""
        h, w = area.shape[:2]
        area[:] = (25, 25, 30)
        LT = cv2.LINE_8
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Header
        cv2.putText(area, "CONSOLE", (6, 16), font, 0.38, (0, 200, 255), 1, LT)
        
        # Compute font params once
        if not hasattr(self, '_cmdcon_params'):
            scale_factor = h / 540
            lh = max(12, int(16 * scale_factor))
            self._cmdcon_params = {
                'font_scale': max(0.28, 0.35 * scale_factor),
                'line_height': lh,
                'max_lines': (h - 24) // max(1, lh)
            }
        
        params = self._cmdcon_params
        visible_lines = self.cmd_console.get_visible_buffer()[-params['max_lines']:]
        
        y = 24 + params['line_height']
        for line in visible_lines:
            # Color code: user commands cyan, responses white
            if line.startswith("> "):
                color = (0, 200, 255)
            elif line.startswith("✅") or line.startswith("🎯"):
                color = (0, 230, 130)
            elif line.startswith("❌") or line.startswith("⚠️"):
                color = (80, 80, 255)
            else:
                color = (200, 200, 210)
            cv2.putText(area, line[:80], (6, y), font, params['font_scale'], color, 1, LT)
            y += params['line_height']

    def _draw_input(self, area):
        h, w = area.shape[:2]
        area[:] = (20, 20, 25)
        LT = cv2.LINE_8
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        y_pos = max(10, int(h * 0.65))
        cv2.putText(area, ">", (6, y_pos), font, 0.45, (0, 200, 255), 1, LT)
        
        input_str = self.cmd_console.get_input()
        cursor = "|" if int(time.time() * 2) % 2 == 0 else ""
        cv2.putText(area, f"{input_str}{cursor}", (20, y_pos), font, 0.45, (230, 230, 235), 1, LT)

# ==========================
#  OPEN/CLOSE (envuelve ControlLink)
# ==========================
def open_port():
    global control
    if control is None:
        raise RuntimeError("ControlLink no inicializado")
    try:
        control.open()
        port_info = control._resolved_port or control.wifi_ip
        print(f"[CTRL] Conexion abierta ({control.mode}) -> {port_info}")
    except Exception as e:
        print(f"[CTRL] Error abriendo conexion: {e}")
        raise

def close_port():
    global control
    if control is None:
        return
    try:
        control.close()
        print(f"[CTRL] Conexion cerrada ({control.mode})")
    except Exception as e:
        print(f"[CTRL] Error cerrando conexion: {e}")

# ==========================
#  IA PARA ELEGIR ID
# ==========================
async def choose_id_with_openai_async(user_prompt: str, info: str, proc: VideoProcessor = None):
    """Async LLM call to choose a person/marker ID based on user command and detection data.
    Uses JSON response format for reliable parsing. Supports clothing, position, name queries."""
    from openai import AsyncOpenAI
    import json as _json
    
    # --- DEBUG: show what the LLM receives ---
    print(f"\n[LLM DEBUG] User command: '{user_prompt}'")
    print(f"[LLM DEBUG] Detection info ({len(info)} chars):")
    print(info if info else "  (EMPTY - no detections!)")
    if proc:
        proc.console.add_output(f"[DEBUG] Comando: '{user_prompt}'")
        proc.console.add_output(f"[DEBUG] Info al LLM:\n{info if info else '(VACIO)'}")
    
    if not info or not info.strip():
        print("[LLM DEBUG] WARNING: info is empty, LLM has no detections to choose from!")
        if proc:
            proc.cmd_console.add_output("No hay detecciones activas para enviar al LLM")
        return None
    
    system_prompt = """You are a navigation assistant for a drone/robot that tracks people.
Your job: given a user command and a list of detected persons with their attributes, return the correct person ID as JSON.

Each person has these attributes:
- person_N: the unique ID (e.g. person_1, person_2)
- Name: face recognition identity (if known)
- Position: where they are in the frame (far left, left, center, right, far right)
- Distance: how far they are in meters
- Angle_X: horizontal angle in degrees (negative=left, positive=right)
- Upper_clothing: color of their shirt/jacket/upper body
- Lower_clothing: color of their pants/skirt/lower body
- Posture: standing, sitting, crouching, or unknown
- Facing: facing camera, angled, or facing away
- Size_in_frame: very close/tall, large, medium, small/far (how big they appear)
- Visibility: torso visibility state (full_torso, partial, upper_only, etc.)
- Movement: whether they are moving left/right or getting closer/farther (omitted if stationary)
- Nearby objects: objects detected near them (backpack, cell phone, etc.)

DECISION RULES (in priority order):
1. If the user says a specific ID like "person 1", "persona 2" → return that ID directly
2. If the user says a NAME like "go to John", "find María" → match against the Name field
3. If the user describes CLOTHING like "the one in red", "persona de azul", "guy with black shirt" → match Upper_clothing and Lower_clothing
4. If the user says POSITION like "the one on the left", "el de la derecha", "center" → match Position field
5. If the user describes POSTURE like "the sitting one", "el que está sentado", "standing person" → match Posture field
6. If the user describes ORIENTATION like "the one facing me", "el que está de espaldas" → match Facing field
7. If the user describes SIZE like "the tall one", "the big one", "el pequeño" → match Size_in_frame field
8. If the user says "closest", "nearest", "más cercano" → pick the person with smallest Distance
9. If the user says "farthest", "más lejano" → pick the person with largest Distance
10. If the user mentions an OBJECT like "person with backpack", "the one with the phone" → match Nearby objects
11. If the user describes MOVEMENT like "the one coming closer", "el que se mueve a la derecha" → match Movement
12. For generic commands like "go to person", "ve a la persona", "navigate" → pick the closest person
13. If the user says "follow", "sigue", "track", "síguelo" → set follow=true

RESPOND WITH ONLY THIS JSON (no explanation, no markdown):
{"id": "person_N", "follow": false}

Examples:
- "go to person 1" → {"id": "person_1", "follow": false}
- "follow the person in blue" → {"id": "person_2", "follow": true}  (if person_2 wears blue)
- "ve al más cercano" → {"id": "person_1", "follow": false}  (if person_1 is closest)
- "sigue a Juan" → {"id": "person_3", "follow": true}  (if person_3 is named Juan)
- "go to the sitting person" → {"id": "person_2", "follow": false}  (if person_2 is sitting)
- "the one facing away" → {"id": "person_1", "follow": false}  (if person_1 is facing away)

NEVER return null if there is at least one person detected. Always pick the best match."""

    user_msg = f"""User command: "{user_prompt}"

Detected persons:
{info}

Return JSON:"""

    try:
        _base_url = os.environ.get("OPENAI_BASE_URL", getattr(Config.AI, 'OPENAI_BASE_URL', None))
        _api_key = os.environ.get("OPENAI_API_KEY", getattr(Config.AI, 'OPENAI_API_KEY', None))
        _model = os.environ.get("OPENAI_MODEL", getattr(Config.AI, 'OPENAI_MODEL', "gpt-4o-mini"))

        async_client = AsyncOpenAI(api_key=_api_key, base_url=_base_url)
        try:
            response = await asyncio.wait_for(
                async_client.chat.completions.create(
                    model=_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg}
                    ],
                    temperature=0.1,
                    max_tokens=50,
                    timeout=15
                ),
                timeout=20
            )
        finally:
            await async_client.close()
        raw_answer = response.choices[0].message.content.strip()
        print(f"[LLM DEBUG] Raw response: '{raw_answer}'")
        if proc:
            proc.cmd_console.add_output(f"IA respuesta: {raw_answer}")
        
        # --- Parse JSON response ---
        follow_mode = False
        chosen_id = None
        
        # Try JSON parsing first
        try:
            # Clean potential markdown code blocks
            clean = raw_answer.strip('` \t\n')
            if clean.startswith('json'):
                clean = clean[4:].strip()
            # Find JSON object in the response
            json_match = re.search(r'\{[^}]+\}', clean)
            if json_match:
                data = _json.loads(json_match.group())
                chosen_id = data.get('id', data.get('ID', data.get('person', None)))
                follow_mode = data.get('follow', data.get('Follow', False))
                if isinstance(follow_mode, str):
                    follow_mode = follow_mode.lower() in ('true', '1', 'yes', 'si')
                print(f"[LLM DEBUG] JSON parsed: id={chosen_id}, follow={follow_mode}")
        except (_json.JSONDecodeError, AttributeError):
            print(f"[LLM DEBUG] JSON parse failed, falling back to text parsing")
        
        # Fallback: text-based parsing (for models that don't follow JSON format)
        if chosen_id is None:
            answer = raw_answer.strip('"\'` \t\n')
            if answer.lower() in ('none', 'null', 'n/a', ''):
                print(f"[LLM DEBUG] Response is None/empty -> returning None")
                return None
            
            answer_lower = answer.lower().replace(' ', '_')
            
            # Check for follow mode in text
            if answer_lower.startswith('-'):
                follow_mode = True
                answer_lower = answer_lower[1:]
            
            # Find person_N pattern
            person_match = re.search(r'person[a]?[_\s]?(\d+)', answer_lower)
            if person_match:
                chosen_id = f"person_{person_match.group(1)}"
            else:
                # Broader: "person" ... number
                person_search = re.search(r'person[a]?\D*(\d+)', answer_lower)
                if person_search:
                    chosen_id = f"person_{person_search.group(1)}"
                else:
                    # Single number fallback — always produce string person_N
                    all_nums = re.findall(r'\d+', answer)
                    if len(all_nums) == 1:
                        chosen_id = f"person_{all_nums[0]}"
                    elif len(all_nums) > 1:
                        # Multiple numbers — pick the first as person ID
                        chosen_id = f"person_{all_nums[0]}"
        
        if chosen_id is None:
            print(f"[LLM DEBUG] FAILED to parse any ID from: '{raw_answer}'")
            if proc:
                proc.cmd_console.add_output(f"No se pudo parsear ID de: '{raw_answer}'")
            return None
        
        # Normalize person ID format
        if isinstance(chosen_id, str):
            # Ensure consistent format
            pm = re.search(r'person[a]?[_\s]?(\d+)', chosen_id.lower())
            if pm:
                chosen_id = f"person_{pm.group(1)}"
        
        result = ('-' + chosen_id) if (follow_mode and isinstance(chosen_id, str)) else chosen_id
        if isinstance(chosen_id, int) and follow_mode:
            result = -chosen_id
        print(f"[LLM DEBUG] Final result: {result}")
        return result
        
    except Exception as e:
        print(f"[LLM DEBUG] Exception: {str(e)}")
        if proc:
            proc.cmd_console.add_output(f"Error LLM: {str(e)}")
        return None

def format_detection_info(proc: VideoProcessor) -> str:
    """Formatea la información para la IA - soporta personas y marcadores.
    Includes rich attributes derived from already-computed data (zero extra GPU cost)."""
    lines = []
    frame_h = proc.frame_height or 720
    with proc.lock:
        active = proc._get_active_markers()
        for mid in active:
            d = proc.history[mid]
            
            # Format differently for persons vs markers
            if isinstance(mid, str) and mid.startswith('person_'):
                person_num = mid.split('_')[1]
                torso_info = d.get('torso_state', 'unknown')
                pos_label = d.get('position_label', _position_label(d['angle_x']))
                upper_c = d.get('upper_color', 'unknown')
                lower_c = d.get('lower_color', 'unknown')
                
                # Derive extra attributes from existing data (free)
                kpts = d.get('keypoints')
                posture = _estimate_posture(kpts) if kpts is not None else 'unknown'
                frontal = d.get('frontal_score', 0.5)
                facing = _facing_label(frontal)
                bbox = d.get('bbox', (0, 0, 0, 0))
                size_label = _relative_height_label(bbox, frame_h)
                
                # Movement from previous frame
                dist_move = _movement_label(d['distance'], d.get('prev_distance'))
                angle_move = _movement_label(d['angle_x'], d.get('prev_angle_x'))
                
                # Build description line
                desc = f"- person_{person_num}: "
                
                # Face identity
                if mid in proc.face_identities:
                    name, confidence = proc.face_identities[mid]
                    desc += f"Name=\"{name}\" ({confidence:.0%}), "
                
                desc += (
                    f"Position={pos_label}, "
                    f"Distance={d['distance']:.2f}m, "
                    f"Angle_X={d['angle_x']:+.1f}°, "
                    f"Upper_clothing={upper_c}, "
                    f"Lower_clothing={lower_c}, "
                    f"Posture={posture}, "
                    f"Facing={facing}, "
                    f"Size_in_frame={size_label}, "
                    f"Visibility={torso_info}"
                )
                
                # Movement info (only add if meaningful)
                move_parts = []
                if dist_move and dist_move != 'stationary':
                    move_parts.append(f"distance {'closing' if dist_move == 'decreasing' else 'increasing'}")
                if angle_move and angle_move != 'stationary':
                    move_parts.append(f"moving {'right' if angle_move == 'increasing' else 'left'}")
                if move_parts:
                    desc += f", Movement={' & '.join(move_parts)}"
                
                lines.append(desc)
                
                # Add nearby objects
                objs = proc.object_detections.get(mid, [])
                if objs and proc.object_classes:
                    obj_strs = [f"{proc.object_classes[o['class_id']]}" for o in objs]
                    lines.append(f"  Nearby objects: {', '.join(obj_strs)}")
            else:
                lines.append(
                    f"- marker_{mid}: Distance={d['distance']:.2f}m, "
                    f"Angle_X={d['angle_x']:+.1f}°, Angle_Y={d['angle_y']:+.1f}°"
                )
    
    return "\n".join(lines)

# ==========================
#  BYTES DE NAVEGACIÓN (2-byte Arduino protocol)
# ==========================
def _angle_to_mag(angle, threshold):
    """Map angle offset to level 0-3 with safe low-angle behavior.
    Very low angles always use level 1 when movement is needed."""
    a = abs(angle)
    if a < threshold:
        return 0
    # Very low angles above threshold -> always slowest level
    if a < max(threshold * 2.0, threshold + 4.0):
        return 1
    if a < threshold * 4.0:
        return 2
    return 3

def _distance_to_mag(distance, target, fast_threshold):
    """Map distance-to-target into forward level 0-3 with hard safety rule.
    Under 10m, forward speed is ALWAYS level 1 (slowest), if moving forward."""
    gap = distance - target
    if gap <= 0:
        return 0

    # Hard safety requirement from user
    if distance < 10.0:
        return 1

    # Above 10m scale progressively
    if distance < 16.0:
        return 2
    return 3

def _compute_nav_magnitudes(d: dict, target: float, safe_mode: bool = False):
    """Compute per-axis magnitudes with distance/angle adaptive logic and safe caps."""
    ROTATION_THRESHOLD = getattr(Config.Navigation, 'ROTATION_THRESHOLD', 5)
    FAST_DISTANCE = getattr(Config.Navigation, 'FAST_SPEED_THRESHOLD', 1.0)
    VERTICAL_THRESHOLD = getattr(Config.Navigation, 'ROTATION_THRESHOLD', 5)

    ax = d['angle_x']
    ay = d['angle_y']
    dist = d['distance']

    # Rotation
    rot_mag = _angle_to_mag(ax, ROTATION_THRESHOLD)
    ccw_mag = rot_mag if ax <= -ROTATION_THRESHOLD else 0
    cw_mag  = rot_mag if ax >= +ROTATION_THRESHOLD else 0

    # Vertical
    vert_mag = _angle_to_mag(ay, VERTICAL_THRESHOLD)
    up_mag   = vert_mag if ay >= +VERTICAL_THRESHOLD else 0
    down_mag = vert_mag if ay <= -VERTICAL_THRESHOLD else 0

    # Forward/backward
    fwd_mag = _distance_to_mag(dist, target, FAST_DISTANCE)
    bwd_mag = 0

    # Global safety mode: cap every non-zero command to slowest level
    if safe_mode:
        ccw_mag = 1 if ccw_mag > 0 else 0
        cw_mag = 1 if cw_mag > 0 else 0
        up_mag = 1 if up_mag > 0 else 0
        down_mag = 1 if down_mag > 0 else 0
        fwd_mag = 1 if fwd_mag > 0 else 0

    return {
        'ccw': ccw_mag,
        'cw': cw_mag,
        'up': up_mag,
        'down': down_mag,
        'fwd': fwd_mag,
        'bwd': bwd_mag,
        'left': 0,
        'right': 0,
    }

def send_commands_byte(d: dict, target: float):
    """Compute navigation magnitudes and send 2-byte Arduino command."""
    mags = _compute_nav_magnitudes(d, target, safe_mode=get_nav_safe_mode())
    b1, b2 = encode_arduino_pair(
        ccw=mags['ccw'], cw=mags['cw'], up=mags['up'],
        down=mags['down'], fwd=mags['fwd'], bwd=mags['bwd'],
        left=mags['left'], right=mags['right']
    )
    control.send(b1, b2)

_MAG_LABELS = ['---', 'LOW', 'MED', 'MAX']

def print_navigation_commands(d: dict, target: float, follow: bool = False):
    """Display navigation commands with magnitude levels."""
    ax = d['angle_x']
    ay = d['angle_y']
    dist = d['distance']
    header = "SEGUIMIENTO" if follow else "OBJETIVO FIJO"

    mags = _compute_nav_magnitudes(d, target, safe_mode=get_nav_safe_mode())
    ccw = mags['ccw']
    cw = mags['cw']
    up_m = mags['up']
    dn_m = mags['down']
    fwd = mags['fwd']
    lft = mags['left']
    rgt = mags['right']

    gap_str = f"{dist - target:.2f}m restantes" if fwd > 0 else "EN POSICION"
    mode_str = "MODO SEGURO: ON" if get_nav_safe_mode() else "MODO SEGURO: OFF"

    return "\n".join([
        "",
        "===============================",
        f"{header} [ID {d.get('id', '?')}]",
        "===============================",
        f"Dist: {dist:.2f}m (target: {target:.2f}m)",
        f"Dir:  X:{ax:+.1f} Y:{ay:+.1f}",
        "",
        "SERVOS:",
        f"  ROT   CCW:{_MAG_LABELS[ccw]}  CW:{_MAG_LABELS[cw]}",
        f"  TILT  UP:{_MAG_LABELS[up_m]}  DN:{_MAG_LABELS[dn_m]}",
        f"  FWD   {_MAG_LABELS[fwd]}",
        f"  STRAFE L:{_MAG_LABELS[lft]}  R:{_MAG_LABELS[rgt]}",
        f"  -> {gap_str}",
        f"  {mode_str}",
        "===============================",
        "",
    ])

# ==========================
#  VOZ (WHISPER)
# ==========================
def whisper_record_and_transcribe():
    duration = getattr(getattr(Config, 'AI', None), 'WHISPER_DURATION', 4)
    language = getattr(getattr(Config, 'AI', None), 'WHISPER_LANGUAGE', 'es')
    
    # Check for available input device before attempting to record
    try:
        device_info = sd.query_devices(kind='input')
        if device_info is None:
            raise RuntimeError("No input audio device found")
    except Exception as e:
        raise RuntimeError(
            f"No microphone available: {e}\n"
            "  Check that a microphone is connected and enabled in system settings."
        )
    
    print("🎤 Grabando audio (mantén presionada la tecla)...")
    
    audio = sd.rec(int(duration * WHISPER_SAMPLE_RATE), samplerate=WHISPER_SAMPLE_RATE, channels=1, dtype='int16')
    sd.wait()

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    write(temp_file.name, WHISPER_SAMPLE_RATE, audio)
    temp_file.close()

    try:
        print("🧠 Transcribiendo con faster-whisper (4-8x más rápido)...")
        model = get_whisper_model()
        # faster-whisper returns segments, not dict
        segments, info = model.transcribe(temp_file.name, language=language)
        # Combine all segment texts
        text = " ".join([segment.text for segment in segments])
        return text
    finally:
        try:
            os.remove(temp_file.name)
        except Exception as e:
            print(f"⚠️ No se pudo eliminar el archivo temporal: {e}")

def voice_input_thread(proc: VideoProcessor):
    while not proc.stop_event.is_set():
        if not proc.voice_enabled:
            time.sleep(0.1)
            continue

        if not keyboard.is_pressed(Config.Keybinds.KEY_VOICE_RECORD):
            time.sleep(0.1)
            continue

        try:
            texto = whisper_record_and_transcribe()
            if texto and texto.strip():
                print(f"[VOZ] {texto}")
                proc.cmd_console.add_output(f"[VOZ] {texto}")
                proc.cmd_console.submit_command(texto)
            else:
                print("🤷 No se detectó ningún texto.")
                proc.cmd_console.add_output("🤷 No se detectó ningún texto.")
        except Exception as e:
            print(f"❌ Error al transcribir: {e}")
            proc.cmd_console.add_output(f"❌ Error al transcribir: {e}")

        time.sleep(0.5)

# ==========================
#  ENROLLMENT COMMAND PARSING
# ==========================
# Matches: "save person 1 as Yoyo", "add person_2 as Maria", "guardar persona 3 como Juan"
ENROLL_RE = re.compile(
    r'(?:save|add|guardar|registrar|remember|name|nombrar)\s+'
    r'person[a]?[_\s]?(\d+)\s+'
    r'(?:as|como|=)\s+'
    r'(.+)',
    re.IGNORECASE
)

# Flexible enrollment matcher (no ID required):
# "save a person as Basaldua", "guardar persona como Juan", "save as Yoyo"
ENROLL_FLEX_RE = re.compile(
    r'(?:save|add|guardar|registrar|remember|name|nombrar)\s+'
    r'(?:(?:a|an|una|un)\s+)?'
    r'(?:(?:person[a]?|persona)(?:[_\s]?(\d+))?)?\s*'
    r'(?:as|como|=)\s+'
    r'(.+)',
    re.IGNORECASE
)

ENROLL_INTENT_VERB_RE = re.compile(
    r'\b(?:save|add|enroll|register|remember|name|store|'
    r'guardar|agregar|añadir|anadir|registrar|nombrar|memoriza|guardarle)\b',
    re.IGNORECASE
)

ENROLL_TARGET_HINT_RE = re.compile(
    r'\b(?:face|cara|rostro|person|persona|id\s*\d+)\b',
    re.IGNORECASE
)

def _extract_enroll_name(command: str) -> str:
    """Extract enrollment name from command using several natural-language patterns."""
    cmd = command.strip()
    patterns = [
        r'(?:as|como|=)\s*["\']?([A-Za-zÀ-ÿ0-9 _\-]{2,40})["\']?\s*$',
        r'(?:named|name\s+it|llamad[oa]|se\s+llama)\s+["\']?([A-Za-zÀ-ÿ0-9 _\-]{2,40})["\']?\s*$',
        r'^(?:save|add|enroll|register|name|store|guardar|agregar|añadir|anadir|registrar|nombrar)\s+'
        r'(?:a\s+|an\s+|una\s+|un\s+)?(?:person[a]?|persona|face|cara|rostro)?\s*'
        r'["\']?([A-Za-zÀ-ÿ0-9 _\-]{2,40})["\']?\s*$',
    ]
    for pat in patterns:
        m = re.search(pat, cmd, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            # reject obvious non-name tokens
            bad = {
                'person', 'persona', 'face', 'cara', 'rostro', 'id',
                'as', 'como', 'save', 'add', 'enroll', 'register',
                'guardar', 'agregar', 'añadir', 'anadir', 'nombrar'
            }
            if candidate.lower() not in bad and len(candidate) >= 2:
                return candidate
    return ''

def detect_enrollment_intent(command: str):
    """Detect if user intends to enroll/save a face and extract target info.

    Returns:
      None if not enrollment intent
      dict with keys: {'person_num': str|None, 'target_name': str|None, 'reason': str}
    """
    cmd = command.strip()
    if not cmd:
        return None

    has_enroll_verb = bool(ENROLL_INTENT_VERB_RE.search(cmd))
    explicit_as_form = bool(re.search(r'\b(?:as|como|=)\b', cmd, re.IGNORECASE))
    has_target_hint = bool(ENROLL_TARGET_HINT_RE.search(cmd))

    # Enrollment intent if user uses enrollment verbs and any reasonable target syntax
    if not (has_enroll_verb and (explicit_as_form or has_target_hint or len(cmd.split()) <= 6)):
        return None

    person_num = None
    pm = re.search(r'\b(?:person[a]?|id)[_\s\-]?(\d+)\b', cmd, re.IGNORECASE)
    if pm:
        person_num = pm.group(1)

    target_name = _extract_enroll_name(cmd)
    return {
        'person_num': person_num,
        'target_name': target_name if target_name else None,
        'reason': 'enroll_intent_detected'
    }

# ==========================
#  ENHANCE / ADD ANGLE COMMAND PARSING
# ==========================
# Verbs that signal the user wants to add a NEW perspective of an EXISTING person
ENHANCE_VERB_RE = re.compile(
    r'\b(?:enhance|update|improve|retrain|upgrade|refine|'
    r'mejorar|actualizar|reentrenar|refinar)\b',
    re.IGNORECASE
)

# Explicit "add angle / add perspective / add view" patterns
ENHANCE_ANGLE_RE = re.compile(
    r'\b(?:add|agregar|añadir|anadir)\s+'
    r'(?:(?:a|an|una?|new|nuevo|nueva|more|otra?)\s+)*'
    r'(?:angle|perspective|view|face|photo|foto|vista|ángulo|angulo|perspectiva|cara)\b',
    re.IGNORECASE
)

# Extract the target name from enhance commands
# "enhance Yoyo", "add angle for Yoyo", "improve Yoyo's face", "mejorar a Yoyo"
ENHANCE_NAME_PATTERNS = [
    # "for/of/de/a/para NAME"
    r'(?:for|of|de|a|para)\s+["\']?([A-Za-zÀ-ÿ0-9 _\-]{2,40}?)(?:["\']?\s*(?:\'s)?\s*(?:face|cara|rostro|recognition|reconocimiento)?)\s*$',
    # "enhance NAME", "update NAME", "mejorar NAME" (verb then name directly)
    r'(?:enhance|update|improve|retrain|upgrade|refine|mejorar|actualizar|reentrenar|refinar)\s+'
    r'(?:a\s+|el\s+|la\s+|al\s+)?["\']?([A-Za-zÀ-ÿ0-9 _\-]{2,40}?)["\']?\s*'
    r'(?:\'s\s+)?(?:face|cara|rostro|recognition|reconocimiento)?\s*$',
    # "add angle person_N NAME" or just "add angle NAME"
    r'(?:angle|perspective|view|face|photo|foto|vista|ángulo|angulo|perspectiva|cara)\s+'
    r'(?:(?:for|of|de|a|para)\s+)?'
    r'(?:person[a]?[_\s]?\d+\s+)?'
    r'["\']?([A-Za-zÀ-ÿ0-9 _\-]{2,40})["\']?\s*$',
]

def _extract_enhance_name(command: str) -> str:
    """Extract the target name from an enhance/add-angle command."""
    cmd = command.strip()
    bad_tokens = {
        'person', 'persona', 'face', 'cara', 'rostro', 'id',
        'enhance', 'update', 'improve', 'retrain', 'upgrade', 'refine',
        'mejorar', 'actualizar', 'reentrenar', 'refinar',
        'add', 'agregar', 'añadir', 'anadir', 'angle', 'perspective',
        'view', 'photo', 'foto', 'vista', 'ángulo', 'angulo', 'perspectiva',
        'new', 'nuevo', 'nueva', 'more', 'otra', 'otro', 'a', 'an',
        'for', 'of', 'de', 'para', 'the', 'el', 'la', 'al', 'recognition',
        'reconocimiento', 'it', 'lo', 's',
    }
    for pat in ENHANCE_NAME_PATTERNS:
        m = re.search(pat, cmd, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip().rstrip("'")
            if candidate.lower() not in bad_tokens and len(candidate) >= 2:
                return candidate
    return ''


def detect_enhance_intent(command: str):
    """Detect if user wants to add a new perspective/angle of an EXISTING person.

    Returns:
      None if not enhance intent
      dict with keys: {'target_name': str|None, 'person_num': str|None, 'reason': str}
    """
    cmd = command.strip()
    if not cmd:
        return None

    has_enhance_verb = bool(ENHANCE_VERB_RE.search(cmd))
    has_angle_phrase = bool(ENHANCE_ANGLE_RE.search(cmd))

    if not (has_enhance_verb or has_angle_phrase):
        return None

    person_num = None
    pm = re.search(r'\b(?:person[a]?|id)[_\s\-]?(\d+)\b', cmd, re.IGNORECASE)
    if pm:
        person_num = pm.group(1)

    target_name = _extract_enhance_name(cmd)
    return {
        'target_name': target_name if target_name else None,
        'person_num': person_num,
        'reason': 'enhance_intent_detected',
    }


# Matches: "remove Yoyo", "delete Maria", "borrar Juan", "eliminar persona Maria"
REMOVE_FACE_RE = re.compile(
    r'(?:remove|delete|borrar|eliminar)\s+(?:face|persona|person)?\s*(.+)',
    re.IGNORECASE
)

# Matches: "rename Yoyo to Yosef", "renombrar Maria a MariaG"
RENAME_FACE_RE = re.compile(
    r'(?:rename|renombrar|cambiar\s+nombre)\s+(.+?)\s+(?:to|a|->|→)\s+(.+)',
    re.IGNORECASE
)

def _resolve_name_to_person(proc, name: str):
    """Find a tracked person_id by their recognised face name.
    Returns person_id string or None."""
    name_lower = name.lower().strip()
    with proc.lock:
        for pid, (face_name, _sim) in proc.face_identities.items():
            if face_name.lower() == name_lower:
                return pid
    return None

# ==========================
#  FIND PERSON (360° SCAN)
# ==========================
# Duration (seconds) for one full slow rotation (CW level 1).
# Adjust if the physical platform rotates faster or slower.
FIND_SCAN_DURATION = 18.0
# Interval between checks during scan (seconds)
FIND_SCAN_CHECK_INTERVAL = 0.4

def _find_person_scan(proc, name: str):
    """Rotate slowly (CW level 1) for up to FIND_SCAN_DURATION seconds,
    checking face_identities every FIND_SCAN_CHECK_INTERVAL for *name*.
    If found, stop and prompt follow/go-to.  If not found after a full
    rotation, stop and report."""
    found_pid = None
    try:
        open_port()
        start = time.time()
        # Slow CW rotation: channel 1 (CW) at magnitude 1
        b1, b2 = encode_arduino_pair(cw=1)

        while not proc.stop_event.is_set():
            elapsed = time.time() - start
            if elapsed >= FIND_SCAN_DURATION:
                break

            # Check if target is visible
            with proc.lock:
                for pid, (face_name, _sim) in list(proc.face_identities.items()):
                    if face_name.lower() == name.lower() and pid in proc.history:
                        found_pid = pid
                        break

            if found_pid:
                break

            # Cancel if user presses 5
            if keyboard.is_pressed(Config.Keybinds.KEY_CANCEL_NAV):
                proc.cmd_console.add_output("🛑 Find scan cancelled.")
                if proc.tts_enabled:
                    tts_speak("Search cancelled")
                return

            # Send slow rotation command
            control.send(b1, b2)
            time.sleep(FIND_SCAN_CHECK_INTERVAL)

        # Stop rotation
        control.send(0, 0)

    except Exception as e:
        proc.cmd_console.add_output(f"❌ Find scan error: {e}")
        try:
            control.send(0, 0)
        except Exception:
            pass
        return
    finally:
        try:
            close_port()
        except Exception:
            pass

    if found_pid:
        person_num = found_pid.split('_')[1]
        dist_info = proc.history.get(found_pid, {}).get('distance', 0)
        proc.cmd_console.add_output(
            f"✅ Found '{name}' ({found_pid}) at {dist_info:.2f}m!\n"
            f"   Type 'go' to navigate or 'follow' to track:"
        )
        if proc.tts_enabled:
            tts_speak(f"Found {name}")
        # Wait for user response (go / follow / cancel)
        proc._find_person_choice = found_pid
    else:
        proc.cmd_console.add_output(f"❌ '{name}' not found after 360° scan.")
        if proc.tts_enabled:
            tts_speak(f"{name} not found")

# ==========================
#  PROMPT THREAD (SELECCIÓN Y NAVEGACIÓN)
# ==========================
def prompt_thread(proc):
    """Command consumer: reads from cmd_queue (Queue) instead of scanning console buffer."""
    while not proc.stop_event.is_set():
        # Block on queue with timeout so we can check stop_event periodically
        try:
            last_command = proc.cmd_console.cmd_queue.get(timeout=0.5)
        except Empty:
            continue

        # ─── Handle pending enrollment confirmation ─────────────────
        if proc.pending_enrollment is not None:
            pe = proc.pending_enrollment
            cmd_low = last_command.strip().lower()
            
            # Check for timeout (30 seconds)
            if time.time() - pe['ts'] > 30:
                proc.pending_enrollment = None
                proc.cmd_console.add_output("⏰ Enrollment timed out.")
                continue
            
            if cmd_low in ('y', 'yes', 'si', 'sí'):
                # Execute enrollment (same path for new & enhance — add_face appends)
                pid = pe['person_id']
                name = pe['name']
                is_enhance = pe.get('enhance', False)
                action_label = "Enhancing" if is_enhance else "Enrolling"
                proc.cmd_console.add_output(f"📸 {action_label} {pid} as '{name}'...")
                
                with proc.lock:
                    person_data = proc.history.get(pid)
                    raw_frame = proc._raw_frame
                
                if person_data is None:
                    proc.cmd_console.add_output(f"❌ {pid} ya no es visible. Intenta de nuevo.")
                elif raw_frame is None:
                    proc.cmd_console.add_output("❌ No hay frame disponible.")
                elif proc.face_system is None:
                    proc.cmd_console.add_output("❌ Face recognition not loaded.")
                else:
                    kpts = person_data.get('keypoints')
                    ok, msg = proc.face_system.enroll_person(raw_frame, kpts, name)
                    if ok:
                        if is_enhance:
                            proc.cmd_console.add_output(f"✅ New angle added — {msg}")
                        else:
                            proc.cmd_console.add_output(f"✅ {msg}")
                        # Immediately tag this person
                        with proc.lock:
                            proc.face_identities[pid] = (name, 1.0)
                    else:
                        proc.cmd_console.add_output(f"❌ {msg}")
                
                proc.pending_enrollment = None
                continue
            
            elif cmd_low in ('n', 'no'):
                proc.pending_enrollment = None
                proc.cmd_console.add_output("❌ Enrollment cancelled.")
                continue
            else:
                # Any other command cancels enrollment implicitly
                proc.pending_enrollment = None
                proc.cmd_console.add_output("⚠️ Enrollment cancelled (new command).")
                # Fall through to process the new command normally

        # ─── Handle pending FIND PERSON name input ──────────────────
        if getattr(proc, '_find_person_pending', False):
            proc._find_person_pending = False
            target_name = last_command.strip()
            if proc.face_system:
                known = proc.face_system.list_people()
                # Case-insensitive match
                actual_name = None
                for kn in known:
                    if kn.lower() == target_name.lower():
                        actual_name = kn
                        break
                if actual_name:
                    proc.cmd_console.add_output(f"🔎 Scanning for '{actual_name}'...")
                    if proc.tts_enabled:
                        tts_speak(f"Searching for {actual_name}")
                    threading.Thread(
                        target=_find_person_scan,
                        args=(proc, actual_name),
                        daemon=True,
                    ).start()
                else:
                    proc.cmd_console.add_output(
                        f"❌ '{target_name}' not in database. Known: {', '.join(known)}"
                    )
            continue

        # ─── Handle pending FIND PERSON go/follow choice ────────────
        if getattr(proc, '_find_person_choice', None) is not None:
            choice = last_command.strip().lower()
            pid = proc._find_person_choice
            proc._find_person_choice = None

            if choice in ('go', 'ir', 've', 'navigate'):
                person_num = pid.split('_')[1]
                proc.cmd_console.submit_command(f"go to person {person_num}")
            elif choice in ('follow', 'sigue', 'seguir', 'track', 'f'):
                person_num = pid.split('_')[1]
                proc.cmd_console.submit_command(f"follow person {person_num}")
            else:
                proc.cmd_console.add_output("⚠️ Find cancelled. (Expected 'go' or 'follow')")
            continue

        # ─── Check for ENHANCE / ADD-ANGLE intent (before enrollment) ─
        enhance_intent = detect_enhance_intent(last_command)
        if enhance_intent:
            if not proc.face_system:
                proc.cmd_console.add_output("❌ Face recognition not loaded.")
                continue

            target_name = (enhance_intent.get('target_name') or '').strip()
            person_num = enhance_intent.get('person_num')

            # If no name was parsed, ask the user
            if not target_name:
                known = proc.face_system.list_people()
                known_str = ', '.join(known) if known else '(empty)'
                proc.cmd_console.add_output(
                    "❌ ¿A quién quieres mejorar? Faltó el nombre.\n"
                    f"   Personas conocidas: {known_str}\n"
                    "   Ejemplo: 'add angle for Yoyo' o 'enhance Yoyo'"
                )
                continue

            # Verify the person already exists in the face database
            known = proc.face_system.list_people()
            actual_name = None
            for kn in known:
                if kn.lower() == target_name.lower():
                    actual_name = kn
                    break

            if actual_name is None:
                known_str = ', '.join(known) if known else '(empty)'
                proc.cmd_console.add_output(
                    f"❌ '{target_name}' no está en la base de datos.\n"
                    f"   Personas conocidas: {known_str}\n"
                    f"   Para registrar a alguien nuevo usa: 'save person N as {target_name}'"
                )
                continue

            # Resolve which tracked person to capture from
            person_id = None
            if person_num:
                person_id = f"person_{person_num}"
            else:
                # Try to find the person by their already-recognised identity
                person_id = _resolve_name_to_person(proc, actual_name)
                if person_id is None:
                    # Fall back: if exactly one active person, use them
                    with proc.lock:
                        active_people = [
                            pid for pid in proc.history.keys()
                            if isinstance(pid, str) and pid.startswith('person_')
                            and (time.time() - proc.history[pid].get('last_seen', 0) <= proc.expire_time)
                        ]
                    if len(active_people) == 1:
                        person_id = active_people[0]
                        proc.cmd_console.add_output(f"ℹ️ Using {person_id} (only active person)")
                    elif len(active_people) == 0:
                        proc.cmd_console.add_output("❌ No hay personas activas visibles.")
                        continue
                    else:
                        options = ', '.join(active_people)
                        proc.cmd_console.add_output(
                            f"⚠️ Hay múltiples personas activas ({options}).\n"
                            f"   Usa: 'add angle person N for {actual_name}'"
                        )
                        continue

            with proc.lock:
                person_exists = person_id in proc.history

            if not person_exists:
                proc.cmd_console.add_output(f"❌ {person_id} not found. Make sure they're visible.")
                continue

            # Count existing embeddings for context
            n_existing = len(proc.face_system.database.people.get(actual_name, {}).get('embeddings', []))
            proc.pending_enrollment = {
                'person_id': person_id,
                'name': actual_name,
                'ts': time.time(),
                'enhance': True,
            }
            proc.cmd_console.add_output(
                f"📸 Add new angle of '{actual_name}' from {person_id}?\n"
                f"   (currently {n_existing} embedding{'s' if n_existing != 1 else ''})\n"
                f"   Type 'y' to confirm or 'n' to cancel"
            )
            continue

        # ─── Check for enrollment command/intention (robust parser) ─
        enroll_match = ENROLL_RE.match(last_command)
        enroll_flex_match = ENROLL_FLEX_RE.match(last_command)
        enroll_intent = detect_enrollment_intent(last_command)
        if enroll_match or enroll_flex_match or enroll_intent:
            if not proc.face_system:
                proc.cmd_console.add_output("❌ Face recognition not loaded. No se puede guardar rostro.")
                continue

            # Extract target name and optional person number
            if enroll_match:
                person_num = enroll_match.group(1)
                target_name = enroll_match.group(2).strip()
            else:
                if enroll_flex_match:
                    person_num = enroll_flex_match.group(1)
                    target_name = enroll_flex_match.group(2).strip()
                else:
                    person_num = enroll_intent.get('person_num')
                    target_name = (enroll_intent.get('target_name') or '').strip()

            if not target_name:
                proc.cmd_console.add_output(
                    "❌ Entendí que quieres guardar una persona, pero faltó el nombre.\n"
                    "   Ejemplos: 'save person 1 as Basaldua' o 'save a person as Basaldua'"
                )
                continue

            # Resolve person ID:
            # 1) explicit person number in command
            # 2) if exactly one active person, use it automatically
            # 3) otherwise ask user to be specific and STOP (do not navigate)
            person_id = None
            if person_num:
                person_id = f"person_{person_num}"
            else:
                with proc.lock:
                    active_people = [
                        pid for pid in proc.history.keys()
                        if isinstance(pid, str) and pid.startswith('person_')
                        and (time.time() - proc.history[pid].get('last_seen', 0) <= proc.expire_time)
                    ]

                if len(active_people) == 1:
                    person_id = active_people[0]
                    proc.cmd_console.add_output(f"ℹ️ Enrollment sin ID explícito: usando {person_id}")
                elif len(active_people) == 0:
                    proc.cmd_console.add_output("❌ No hay personas activas visibles para guardar rostro.")
                    continue
                else:
                    options = ', '.join(active_people)
                    proc.cmd_console.add_output(
                        f"⚠️ Hay múltiples personas activas ({options}).\n"
                        f"   Usa: save person N as {target_name}"
                    )
                    continue

            with proc.lock:
                person_exists = person_id in proc.history

            if not person_exists:
                proc.cmd_console.add_output(f"❌ {person_id} not found. Make sure they're visible.")
                continue

            proc.pending_enrollment = {
                'person_id': person_id,
                'name': target_name,
                'ts': time.time()
            }
            proc.cmd_console.add_output(
                f"📸 Save {person_id} as '{target_name}'?\n"
                f"   Type 'y' to confirm or 'n' to cancel"
            )
            continue

        # ─── Check for face rename command ──────────────────────────
        rename_match = RENAME_FACE_RE.match(last_command)
        if rename_match and proc.face_system:
            old_name = rename_match.group(1).strip()
            new_name = rename_match.group(2).strip()
            known = proc.face_system.list_people()
            # Find case-insensitive match for old name
            actual_old = None
            for kn in known:
                if kn.lower() == old_name.lower():
                    actual_old = kn
                    break
            if actual_old:
                proc.face_system.database.rename_person(actual_old, new_name)
                # Update live identity references
                proc.face_system.clear_cache()
                with proc.lock:
                    for pid in list(proc.face_identities.keys()):
                        if proc.face_identities[pid][0] == actual_old:
                            proc.face_identities[pid] = (new_name, proc.face_identities[pid][1])
                proc.cmd_console.add_output(f"✅ Renamed '{actual_old}' → '{new_name}'")
            else:
                proc.cmd_console.add_output(f"❌ '{old_name}' not found. Known: {', '.join(known) if known else '(empty)'}")
            continue

        # ─── Check for face removal command ─────────────────────────
        remove_match = REMOVE_FACE_RE.match(last_command)
        if remove_match and proc.face_system:
            target_name = remove_match.group(1).strip()
            known = proc.face_system.list_people()
            # Find case-insensitive match
            actual_name = None
            for kn in known:
                if kn.lower() == target_name.lower():
                    actual_name = kn
                    break
            if actual_name:
                proc.face_system.remove_person(actual_name)
                # Clear identity from any tracked person
                with proc.lock:
                    for pid in list(proc.face_identities.keys()):
                        if proc.face_identities[pid][0] == actual_name:
                            del proc.face_identities[pid]
                proc.cmd_console.add_output(f"✅ Removed '{actual_name}' from face database.")
            else:
                proc.cmd_console.add_output(f"❌ '{target_name}' not found in database. Known: {', '.join(known) if known else '(empty)'}")
            continue

        if last_command == Config.Keybinds.KEY_MANUAL_TOGGLE:
            with proc.manual_mode_lock:
                proc.manual_mode = not proc.manual_mode
                entering_manual = proc.manual_mode
            
            if entering_manual:
                proc.cmd_console.add_output("🔧 MODO MANUAL ACTIVADO...")
                try:
                    manual_control_loop(proc)        # opens/closes port internally
                    proc.cmd_console.add_output("🔧 MODO MANUAL DESACTIVADO")
                    last_command = None 
                except serial.SerialException as e:
                    proc.cmd_console.add_output(f"❌ Error al abrir el puerto: {e}")
                    with proc.manual_mode_lock:
                        proc.manual_mode = False
                    continue
            else:
                close_port()
            proc.cmd_console.clear_input()
            continue

        # si estamos en modo manual, ignorar IA
        with proc.manual_mode_lock:
            if proc.manual_mode:
                continue
        proc.cmd_console.add_output("\n🔍 Procesando solicitud (async - no bloquea UI)...")
        
        info = format_detection_info(proc)
        
        # ─── Name-based fast-path: "go to Yoyo" → resolve name to person_id ───
        # Check if the command references a known face name
        name_resolved_id = None
        if proc.face_system and proc.face_identities:
            follow_keywords = ['follow', 'sigue', 'track', 'persigue', 'stay with', 'quedarse']
            cmd_lower = last_command.lower()
            is_follow = any(kw in cmd_lower for kw in follow_keywords)
            
            # Try each known name against the command
            for pid, (face_name, _sim) in list(proc.face_identities.items()):
                if face_name.lower() in cmd_lower:
                    # Verify person is still active
                    with proc.lock:
                        if pid in proc.history:
                            name_resolved_id = f"-{pid}" if is_follow else pid
                            proc.cmd_console.add_output(
                                f"👤 '{face_name}' identificado como {pid}"
                            )
                            break
        
        # --- Fast-path: skip LLM when only 1 person detected ---
        chosen_id = name_resolved_id  # May be None or already resolved by name
        if chosen_id is None:
            with proc.lock:
                active = proc._get_active_markers()
                person_ids = [m for m in active if isinstance(m, str) and m.startswith('person_')]
            
            if len(person_ids) == 1:
                # Check if command implies follow mode
                follow_keywords = ['follow', 'sigue', 'track', 'persigue', 'stay with', 'quedarse']
                is_follow = any(kw in last_command.lower() for kw in follow_keywords)
                sole_person = person_ids[0]
                if is_follow:
                    chosen_id = f"-{sole_person}"
                else:
                    chosen_id = sole_person
                proc.cmd_console.add_output(f"✅ Único objetivo detectado: {sole_person} (LLM omitido)")
            elif len(person_ids) == 0:
                proc.cmd_console.add_output("⚠️ No hay personas activas detectadas.")
                print(f"[NAV DEBUG] No active persons. Active markers: {active}")
                chosen_id = None
            else:
                # Multiple persons or markers — use LLM
                print(f"[NAV DEBUG] {len(person_ids)} persons detected: {person_ids}")
                proc.console.add_output(f"[DEBUG] {len(person_ids)} personas activas: {person_ids}")
                _loop = asyncio.new_event_loop()
                try:
                    chosen_id = _loop.run_until_complete(
                        choose_id_with_openai_async(last_command, info, proc)
                    )
                finally:
                    _loop.close()
        print(f"ID elegido: {chosen_id}")
        proc.cmd_console.add_output(F"🔍 Seleccionado ID: {chosen_id if chosen_id is not None else 'Ninguno'}")
        
        if chosen_id is None:
            proc.cmd_console.add_output("❌ No se identificó un objetivo claro.\nIntenta ser más específico.")
            continue
        else:
            # Handle both string (person_1) and int (marker ID) formats
            follow = False
            if isinstance(chosen_id, str):
                # String format: check for negative prefix (follow mode)
                if chosen_id.startswith('-'):
                    follow = True
                    chosen_id = chosen_id[1:]  # Remove '-' prefix
                    proc.cmd_console.add_output("MODO TRACKEO: SIGUIENDO OBJETIVO")
                else:
                    proc.cmd_console.add_output("MODO NAVIGACIÓN: LLEGANDO A OBJETIVO")
            else:
                # Integer format (legacy ArUco markers)
                if chosen_id < 0:
                    follow = True
                    proc.cmd_console.add_output("MODO TRACKEO: SIGUIENDO OBJETIVO")
                    chosen_id = abs(chosen_id)
                elif chosen_id > 0:
                    follow = False
                    proc.cmd_console.add_output("MODO NAVIGACIÓN: LLEGANDO A OBJETIVO")

        # Iniciar navegación
        with proc.lock:
            proc.selected_id = chosen_id  # Can be string or int now
            proc.guided_mode = True
            marker_info = proc.history.get(chosen_id, {})
            
            # Format target name
            if isinstance(chosen_id, str) and chosen_id.startswith('person_'):
                target_name = f"Person {chosen_id.split('_')[1]}"
                # Use face name if available
                if chosen_id in proc.face_identities:
                    target_name = proc.face_identities[chosen_id][0]
            else:
                target_name = f"Marker {chosen_id}"
            
            proc.cmd_console.add_output(f"""
🎯 MODO NAVEGACIÓN ACTIVADO ({target_name})
   Distancia: {marker_info.get('distance', 0):.2f}m
   Dirección: X:{marker_info.get('angle_x', 0):+.1f}° Y:{marker_info.get('angle_y', 0):+.1f}°
""")
            # F4: TTS announce navigation start
            if proc.tts_enabled:
                mode_word = "Following" if follow else "Navigating to"
                tts_speak(f"{mode_word} {target_name}")
        
        # Bucle de navegación
        connection_lost_time = None
        MAX_CONNECTION_LOSS = getattr(Config.Navigation, 'MARKER_LOST_TIMEOUT', 3.0)
        command_errors = 0
        MAX_COMMAND_ERRORS = 5  # Máximo de errores consecutivos antes de abortar
        
        try:
            open_port()
            while not proc.stop_event.is_set():
                if keyboard.is_pressed(Config.Keybinds.KEY_CANCEL_NAV) or proc.cancel_nav_event.is_set():
                    proc.cancel_nav_event.clear()
                    proc.cmd_console.add_output(f"🛑 MODO NAVEGACIÓN CANCELADO (tecla {Config.Keybinds.KEY_CANCEL_NAV.upper()})")
                    if proc.tts_enabled:
                        tts_speak("Navigation cancelled")
                    break
                    
                with proc.lock:
                    marker_data = proc.history.get(chosen_id)
                    if marker_data:
                        # Copy data while under lock, release lock before I/O
                        marker_data = dict(marker_data)  # shallow copy
                        connection_lost_time = None
                    
                if not marker_data:
                    if connection_lost_time is None:
                        connection_lost_time = time.time()
                        proc.cmd_console.add_output("⚠️ Objetivo perdido, buscando...")
                    elif time.time() - connection_lost_time > MAX_CONNECTION_LOSS:
                        proc.cmd_console.add_output("❌ El objetivo se perdió por más de 3 segundos")
                        if proc.tts_enabled:
                            tts_speak("Target lost")
                        break
                    time.sleep(0.1)
                    continue
                        
                nav_info = print_navigation_commands({'id': chosen_id, **marker_data}, DISTANCE_TARGET, follow)
                proc.console.add_output(nav_info)
                
                # F6: Warn about obstacles in path during navigation
                with proc.lock:
                    nav_obstacles = list(proc.obstacle_detections)
                if nav_obstacles and not hasattr(proc, '_last_obstacle_warn') or \
                   (nav_obstacles and time.time() - getattr(proc, '_last_obstacle_warn', 0) > 5.0):
                    obstacle_names = list(set(o[0] for o in nav_obstacles[:3]))
                    proc.cmd_console.add_output(f"⚠️ Obstacles detected: {', '.join(obstacle_names)}")
                    if proc.tts_enabled:
                        tts_speak(f"Warning, {obstacle_names[0]} ahead")
                    proc._last_obstacle_warn = time.time()
                
                try:
                    send_commands_byte({'id': chosen_id, **marker_data}, DISTANCE_TARGET)
                    command_errors = 0  # Reset error counter on success
                except RuntimeError as e:
                    command_errors += 1
                    proc.cmd_console.add_output(f"⚠️ Error de comunicación ({command_errors}/{MAX_COMMAND_ERRORS}): {e}")
                    if command_errors >= MAX_COMMAND_ERRORS:
                        proc.cmd_console.add_output("❌ Demasiados errores de comunicación, abortando navegación")
                        break
                    time.sleep(0.2)
                    continue
                except Exception as e:
                    proc.cmd_console.add_output(f"❌ Error inesperado: {e}")
                    break

                if not follow:
                    if marker_data['distance'] <= DISTANCE_TARGET:
                        proc.cmd_console.add_output("✅ OBJETIVO ALCANZADO")
                        if proc.tts_enabled:
                            tts_speak("Target reached")
                        break
                        
                time.sleep(0.5)

        except serial.SerialException as e:
            proc.cmd_console.add_output(f"❌ Error de comunicación: {e}")
        except Exception as e:
            proc.cmd_console.add_output(f"❌ Error inesperado: {e}")
        finally:
            close_port()
            with proc.lock:
                proc.guided_mode = False
                proc.selected_id = None

# ==========================
#  CAPTURAS
# ==========================

# Hardcoded scrcpy capture resolution — aligned to calibration/calINSPIRO.npz
# Loaded from config.py SourceConfig; fallback to 2340x1080
SCRCPY_WIDTH  = getattr(getattr(Config, 'Source', None), 'SCRCPY_WIDTH', 2340)
SCRCPY_HEIGHT = getattr(getattr(Config, 'Source', None), 'SCRCPY_HEIGHT', 1080)

# PrintWindow flags — capture window content even when behind other windows
PW_CLIENTONLY = 1           # Capture client area only (no title bar)
PW_RENDERFULLCONTENT = 2    # Force full DWM render (Windows 8.1+)

def capture_window_by_title(title_hint):
    """Capture any window by partial title match (for Smart View, scrcpy, etc)."""
    if not SCRCPY_AVAILABLE:
        return None
    try:
        # Find window by exact or partial title
        hwnd = win32gui.FindWindow(None, title_hint)
        if not hwnd:
            # Search all windows for partial match
            def enum_callback(h, results):
                if win32gui.IsWindowVisible(h):
                    t = win32gui.GetWindowText(h)
                    if t and title_hint.lower() in t.lower():
                        results.append(h)
            results = []
            win32gui.EnumWindows(enum_callback, results)
            if results:
                hwnd = results[0]
            else:
                return None

        left_c, top_c, right_c, bottom_c = win32gui.GetClientRect(hwnd)
        width  = right_c  - left_c
        height = bottom_c - top_c
        if width <= 0 or height <= 0:
            return None

        hwnd_dc = win32gui.GetDC(hwnd)
        mfc_dc  = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)

        # PrintWindow — works even when window is behind other windows
        ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_CLIENTONLY | PW_RENDERFULLCONTENT)

        bmpstr  = save_bitmap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype=np.uint8).reshape(height, width, 4)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        return img
    except Exception as e:
        return None

def capture_scrcpy_window():
    """Capture the scrcpy window via capture_window_by_title + resize to expected resolution."""
    img = capture_window_by_title("scrcpy")
    if img is None:
        return None
    h, w = img.shape[:2]
    if w != SCRCPY_WIDTH or h != SCRCPY_HEIGHT:
        img = cv2.resize(img, (SCRCPY_WIDTH, SCRCPY_HEIGHT))
    return img

def capture_thread(src, frame_q, proc, source_type="default"):
    
    if src == "smartview":
        source_type = "smartview"
        if not SCRCPY_AVAILABLE:
            proc.cmd_console.add_output("Error: pywin32 required for Smart View capture")
            proc.stop_event.set()
            return
        
        config = SOURCE_CONFIGS[source_type]
        proc.frame_time = 1.0 / config["target_fps"]
        
        # Window title hints to search for (Connect app / Conectar / phone name)
        title_hints = ["Connect", "Conectar", "Wireless Display", "Galaxy", "SM-S928"]
        
        proc.cmd_console.add_output("=== Smart View / Miracast ===")
        proc.cmd_console.add_output("1. Abre 'Conectar' en Windows (buscar 'Connect' en Inicio)")
        proc.cmd_console.add_output("2. En tu S24: desliza abajo > Smart View > selecciona tu PC")
        proc.cmd_console.add_output("3. Esperando ventana de transmision...")
        
        found_title = None
        wait_start = time.time()
        
        # Wait up to 60 seconds for the Miracast window to appear
        while not proc.stop_event.is_set() and (time.time() - wait_start) < 60:
            for hint in title_hints:
                test_frame = capture_window_by_title(hint)
                if test_frame is not None:
                    found_title = hint
                    break
            if found_title:
                break
            time.sleep(1)
        
        if not found_title:
            proc.cmd_console.add_output("No se detecto ventana Smart View en 60s")
            proc.cmd_console.add_output("Asegurate de que la app 'Conectar' esta abierta")
            proc.stop_event.set()
            return
        
        proc.cmd_console.add_output(f"Smart View detectado (ventana: '{found_title}')")
        proc.cmd_console.add_output("Capturando pantalla...")
        
        no_frame_count = 0
        while not proc.stop_event.is_set():
            target = time.time() + proc.frame_time
            frame = capture_window_by_title(found_title)
            if frame is not None:
                no_frame_count = 0
                try:
                    frame_q.put_nowait(frame)
                except Full:
                    try:
                        frame_q.get_nowait()
                        frame_q.put_nowait(frame)
                    except Empty:
                        pass
            else:
                no_frame_count += 1
                if no_frame_count > 30:
                    proc.cmd_console.add_output("Smart View window lost. Reconnecting...")
                    found_again = False
                    for hint in title_hints:
                        if capture_window_by_title(hint) is not None:
                            found_title = hint
                            found_again = True
                            no_frame_count = 0
                            proc.cmd_console.add_output(f"Reconectado: '{hint}'")
                            break
                    if not found_again:
                        proc.cmd_console.add_output("Smart View perdido. Deteniendose.")
                        proc.stop_event.set()
                        return
            
            sleep_time = target - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    elif src == "scrcpy":
        source_type = "scrcpy"
        if not SCRCPY_AVAILABLE:
            proc.cmd_console.add_output("Error: pywin32 package required for scrcpy capture")
            proc.stop_event.set()
            return
            
        proc.cmd_console.add_output("Using scrcpy window capture (DJI Spark via Android)")
        proc.cmd_console.add_output("Make sure scrcpy is running (launch_scrcpy_wireless.bat)")
        config = SOURCE_CONFIGS[source_type]
        proc.frame_time = 1.0 / config["target_fps"]
        
        while not proc.stop_event.is_set():
            target = time.time() + proc.frame_time
            frame = capture_scrcpy_window()
            if frame is not None:
                try:
                    frame_q.put_nowait(frame)
                except Full:
                    # Descartar frame viejo si la cola está llena (más rápido)
                    try:
                        frame_q.get_nowait()
                        frame_q.put_nowait(frame)
                    except Empty:
                        pass
            sleep_time = target - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    elif src == "stream" or src.startswith("http"):
        stream_url = SOURCE_CONFIGS["stream"]["url"] if src == "stream" else src
        
        # Use phone_stream config if that's the source type, otherwise stream
        stream_config_key = source_type if source_type in SOURCE_CONFIGS else "stream"
        config = SOURCE_CONFIGS[stream_config_key]
        fps = config["target_fps"]
        proc.frame_time = 1.0 / fps
        
        proc.cmd_console.add_output(f"Stream: {stream_url}")
        proc.cmd_console.add_output(f"Target FPS: {fps}")
        
        # Use raw HTTP MJPEG reader for phone_stream (much more reliable than cv2.VideoCapture)
        if "mjpeg" in stream_url.lower() or source_type == "phone_stream":
            import urllib.request
            
            proc.cmd_console.add_output("Using direct MJPEG reader (low latency)")
            
            stream = None
            reconnect_attempts = 0
            
            while not proc.stop_event.is_set():
                # Connect / reconnect
                if stream is None:
                    try:
                        req = urllib.request.Request(stream_url)
                        stream = urllib.request.urlopen(req, timeout=10)
                        reconnect_attempts = 0
                        proc.cmd_console.add_output("MJPEG stream connected")
                    except Exception as e:
                        reconnect_attempts += 1
                        if reconnect_attempts <= 5:
                            proc.cmd_console.add_output(f"Stream connect failed ({reconnect_attempts}/5): {e}")
                            time.sleep(2)
                            continue
                        else:
                            proc.cmd_console.add_output("Stream connection failed. Giving up.")
                            proc.stop_event.set()
                            return
                
                # Read MJPEG frame by finding JPEG boundaries (FFD8 start, FFD9 end)
                try:
                    buf = b''
                    while not proc.stop_event.is_set():
                        chunk = stream.read(4096)
                        if not chunk:
                            proc.cmd_console.add_output("Stream ended, reconnecting...")
                            stream = None
                            break
                        
                        buf += chunk
                        
                        # Find JPEG start and end markers
                        start = buf.find(b'\xff\xd8')
                        end = buf.find(b'\xff\xd9', start + 2) if start != -1 else -1
                        
                        if start != -1 and end != -1:
                            jpg_data = buf[start:end + 2]
                            buf = buf[end + 2:]  # Keep remainder for next frame
                            
                            # Decode JPEG
                            img_array = np.frombuffer(jpg_data, dtype=np.uint8)
                            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                            
                            if frame is not None:
                                if proc.frame_width and proc.frame_height:
                                    if frame.shape[1] != proc.frame_width or frame.shape[0] != proc.frame_height:
                                        frame = cv2.resize(frame, (proc.frame_width, proc.frame_height))
                                
                                try:
                                    if frame_q.full():
                                        frame_q.get_nowait()
                                    frame_q.put_nowait(frame)
                                except (Full, Empty):
                                    pass
                            
                            # Prevent buffer from growing unbounded
                            if len(buf) > 100000:
                                last_start = buf.rfind(b'\xff\xd8')
                                if last_start > 0:
                                    buf = buf[last_start:]
                                else:
                                    buf = b''
                                    
                except Exception as e:
                    proc.cmd_console.add_output(f"Stream read error: {e}")
                    stream = None
                    time.sleep(1)
        else:
            # Standard OpenCV VideoCapture for non-MJPEG streams
            cap = cv2.VideoCapture(stream_url)
            if not cap.isOpened():
                proc.cmd_console.add_output("Error: Cannot open stream")
                proc.stop_event.set()
                return
            
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            while not proc.stop_event.is_set() and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    proc.cmd_console.add_output("Stream frame error, retrying...")
                    time.sleep(1)
                    continue
                
                if proc.frame_width and proc.frame_height:
                    if frame.shape[1] != proc.frame_width or frame.shape[0] != proc.frame_height:
                        frame = cv2.resize(frame, (proc.frame_width, proc.frame_height))
                
                try:
                    if frame_q.full():
                        frame_q.get_nowait()
                    frame_q.put_nowait(frame)
                except Full:
                    continue
            
            cap.release()
    else:
        try:
            src_idx = int(src) if src else 0
        except:
            src_idx = 0
            
        cap = cv2.VideoCapture(src_idx, cv2.CAP_DSHOW)  # CAP_DSHOW más rápido en Windows
        config = SOURCE_CONFIGS["default"]
        
        # Configuración optimizada de cámara
        if proc.frame_width and proc.frame_height:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, proc.frame_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, proc.frame_height)
        
        # Reducir buffer para menor latencia
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Precalentar: descartar primeros frames (suelen ser oscuros)
        for _ in range(3):
            cap.read()
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = config["target_fps"]
        proc.frame_time = 1.0 / fps
        
        proc.cmd_console.add_output(f"Resolución de cámara: {proc.frame_width}x{proc.frame_height}")
        proc.cmd_console.add_output(f"FPS de cámara: {fps}")
        
        while not proc.stop_event.is_set() and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            try:
                if frame_q.full():
                    frame_q.get_nowait()
                frame_q.put_nowait(frame)
            except Full:
                continue
            # No sleep — cap.read() already blocks until a frame is available
            
        cap.release()
        
    proc.stop_event.set()

# ==========================
#  PROCESSING WORKER
# ==========================
def processing_worker(proc, frame_q):
    """Process frames from queue — every frame is processed (no skip-dequeue waste)."""
    process_count = 0
    last_fps_check = time.time()
    
    while not proc.stop_event.is_set():
        try:
            frame = frame_q.get(timeout=0.05)
        except Empty:
            continue
        
        # Process every frame we pull — no skipping
        try:
            proc.process_frame(frame)
            process_count += 1
        except Exception as e:
            if not hasattr(proc, '_process_error_count'):
                proc._process_error_count = 0
            proc._process_error_count += 1
            if proc._process_error_count <= 5:
                print(f"[ERROR] process_frame failed (#{proc._process_error_count}): {e}")
                import traceback
                traceback.print_exc()
        
        # FPS monitoring (every second) — detection_interval is vestigial
        # because ByteTrack requires .track() every frame for ID continuity.
        now = time.time()
        if now - last_fps_check > 1.0:
            process_count = 0
            last_fps_check = now

# ==========================
#  DISPLAY
# ==========================
def display_thread(proc):
    # Espera optimizada con timeout
    max_wait = 2.0
    start_wait = time.time()
    while not hasattr(proc, 'frame_time'):
        if time.time() - start_wait > max_wait:
            proc.frame_time = 1.0 / 30
            break
        time.sleep(0.05)
    
    delay = 1  # Minimal waitKey delay — render as fast as possible
    
    cv2.namedWindow('SIGO', cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.resizeWindow('SIGO', SCRCPY_WIDTH, SCRCPY_HEIGHT)
    cv2.setWindowProperty('SIGO', cv2.WND_PROP_TOPMOST, 0)
    
    last_frame_time = time.time()
    fps_counter = 0
    displayed_fps = 0
    first_frame = True
    last_rendered_gen = -1
    cached_display = None
    
    while not proc.stop_event.is_set():
        if proc.processed_frame is None:
            # No frame yet — use longer waitKey to avoid CPU spin while still handling keys
            key = cv2.waitKey(30) & 0xFF
            if key == Config.Keybinds.KEY_EXIT:
                proc.stop_event.set()
                break
            continue
        
        first_frame = False
            
        current_time = time.time()
        fps_counter += 1
        if current_time - last_frame_time >= 1.0:
            displayed_fps = fps_counter
            fps_counter = 0
            last_frame_time = current_time
        
        # Only re-render GUI when a new processed frame is available
        current_gen = proc._frame_gen
        if current_gen != last_rendered_gen:
            last_rendered_gen = current_gen
            cached_display = proc._render_gui(proc.processed_frame)
            
            if cached_display is not None:
                # FPS badge on fresh render
                fps_text = f"{displayed_fps} FPS"
                fps_color = (0, 255, 100) if displayed_fps >= 20 else ((0, 200, 255) if displayed_fps >= 10 else (80, 80, 255))
                cv2.putText(cached_display, fps_text, (12, 26), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.50, fps_color, 1, cv2.LINE_8)
                cv2.imshow('SIGO', cached_display)
        
        # waitKey(1) = minimal blocking, just enough for OpenCV event pump
        key = cv2.waitKey(delay) & 0xFF

        if key == Config.Keybinds.KEY_EXIT:  # TAB key
            print("\n🛑 Cerrando SIGO (TAB detectado)...")
            proc.stop_event.set()
            break  # Salir inmediatamente del loop

        # ── EMERGENCY STOP (key 5) — halts ALL movement regardless of state ──
        if key == ord(Config.Keybinds.KEY_CANCEL_NAV):
            proc.cancel_nav_event.set()          # breaks navigation loop
            proc.gesture_nav_target = None       # clear gesture nav
            proc._find_person_pending = False    # cancel find-person prompt
            proc._find_person_choice = None      # cancel find-person choice
            with proc.manual_mode_lock:
                was_manual = proc.manual_mode
                proc.manual_mode = False         # exits manual_control_loop
            # Send stop bytes directly (best-effort, port may not be open)
            try:
                if control and (getattr(control, '_ser', None) and control._ser.is_open
                                or getattr(control, '_sock', None)):
                    control.send(0, 0)
            except Exception:
                pass
            mode_label = []
            if was_manual:
                mode_label.append("manual")
            if proc.guided_mode:
                mode_label.append("navigation")
            proc.cmd_console.add_output(
                f"🛑 EMERGENCY STOP — all movement halted"
                + (f" ({', '.join(mode_label)} cancelled)" if mode_label else "")
            )
            if proc.tts_enabled:
                tts_speak("Emergency stop")
            continue

        with proc.manual_mode_lock:
            if proc.manual_mode:
                continue

        if key == Config.Keybinds.KEY_BACKSPACE:
            proc.cmd_console.backspace()
        elif key == Config.Keybinds.KEY_ENTER:
            if proc.cmd_console.get_input():
                cmd = proc.cmd_console.get_input()
                proc.cmd_console.submit_command(cmd)
        elif key == Config.Keybinds.KEY_FACE_RECOGNITION:
            # Toggle face recognition on/off
            if FACE_RECOGNITION_AVAILABLE:
                proc.face_recognition_enabled = not proc.face_recognition_enabled
                if proc.face_recognition_enabled:
                    if proc.face_system is None:
                        proc.cmd_console.add_output("🔄 Loading face recognition (ArcFace)...")
                        try:
                            db_dir = resolve_face_database_dir()
                            proc.face_system = LiveFaceRecognition(
                                database_dir=db_dir
                            )
                            # Auto-enroll from existing photos in face_database/{Name}/
                            auto_count = proc.face_system.auto_enroll_from_photos()
                            people = proc.face_system.list_people()
                            msg = f"✅ Face recognition ON ({len(people)} enrolled)"
                            if auto_count > 0:
                                msg += f" (+{auto_count} from photos)"
                            proc.cmd_console.add_output(msg)
                            proc.cmd_console.add_output(f"   DB: {db_dir}")
                        except Exception as e:
                            proc.cmd_console.add_output(f"❌ Face recognition error: {e}")
                            proc.face_recognition_enabled = False
                    else:
                        # Re-scan for new photos added while running
                        auto_count = proc.face_system.auto_enroll_from_photos()
                        people = proc.face_system.list_people()
                        msg = f"✅ Face recognition ON ({len(people)} enrolled)"
                        if auto_count > 0:
                            msg += f" (+{auto_count} new from photos)"
                        proc.cmd_console.add_output(msg)
                else:
                    proc.cmd_console.add_output("⏸️ Face recognition OFF")
            else:
                proc.cmd_console.add_output("❌ Face recognition unavailable (onnxruntime + ArcFace model required)")
        elif key == Config.Keybinds.KEY_SAFE_MODE:
            now_safe = toggle_nav_safe_mode()
            if now_safe:
                proc.cmd_console.add_output("🛡️ Modo Seguro ACTIVADO — velocidades más lentas")
            else:
                proc.cmd_console.add_output("⚙️ Modo Seguro DESACTIVADO — velocidades adaptativas")
        elif key == getattr(Config.Keybinds, 'KEY_GESTURE_MODE', ord('8')):
            proc.gesture_mode = not proc.gesture_mode
            if proc.gesture_mode:
                proc.cmd_console.add_output("🤚 Gesture recognition ON (hand raised = come here, both hands = stop)")
                if proc.tts_enabled:
                    tts_speak("Gesture mode activated")
            else:
                proc.cmd_console.add_output("🤚 Gesture recognition OFF")
                proc.gesture_active.clear()
                if proc.tts_enabled:
                    tts_speak("Gesture mode deactivated")
        elif key == getattr(Config.Keybinds, 'KEY_FIND_PERSON', ord('9')):
            if not proc.face_system:
                proc.cmd_console.add_output("❌ Face recognition not loaded. Press 4 first.")
            elif proc.guided_mode:
                proc.cmd_console.add_output("⚠️ Navigation already active. Cancel with 5 first.")
            else:
                # Prompt for name — submit it as a find command
                known = proc.face_system.list_people()
                if not known:
                    proc.cmd_console.add_output("❌ No faces enrolled in database.")
                else:
                    proc.cmd_console.add_output(f"🔎 FIND PERSON — enrolled: {', '.join(known)}")
                    proc.cmd_console.add_output("   Type the name and press Enter:")
                    proc._find_person_pending = True
        elif key in Config.Keybinds.KEY_ARROW_PREFIX:
            key2 = cv2.waitKey(1) & 0xFF
            if key2 == Config.Keybinds.KEY_ARROW_UP:
                proc.cmd_console.history_up()
            elif key2 == Config.Keybinds.KEY_ARROW_DOWN:
                proc.cmd_console.history_down()
        elif 32 <= key <= 126:
            # Skip number-row hotkeys so they don't get typed as text
            hotkey_codes = {
                ord(Config.Keybinds.KEY_VOICE_RECORD),      # 3
                Config.Keybinds.KEY_FACE_RECOGNITION,        # 4
                ord(Config.Keybinds.KEY_CANCEL_NAV),         # 5
                Config.Keybinds.KEY_SAFE_MODE,               # 6
                ord(Config.Keybinds.KEY_MANUAL_TOGGLE),      # 7
                getattr(Config.Keybinds, 'KEY_GESTURE_MODE', ord('8')),  # 8
                getattr(Config.Keybinds, 'KEY_FIND_PERSON', ord('9')),   # 9
            }
            if key not in hotkey_codes:
                proc.cmd_console.add_to_input(chr(key))
        
    cv2.destroyAllWindows()

# ==========================
#  MODO MANUAL
# ==========================
# Keys that map to each Arduino channel (order matches Arduino bit layout)
_MANUAL_CHANNEL_KEYS = [
    'MANUAL_ROTATE_CCW',   # channel 0: CCW rotation
    'MANUAL_ROTATE_CW',    # channel 1: CW rotation
    'MANUAL_UP',           # channel 2: Up
    'MANUAL_DOWN',         # channel 3: Down
    'MANUAL_FORWARD',      # channel 4: Forward
    'MANUAL_BACK',         # channel 5: Backward
    'MANUAL_LEFT',         # channel 6: Strafe left
    'MANUAL_RIGHT',        # channel 7: Strafe right
]

def manual_control_loop(proc: VideoProcessor):
    """
    Manual control loop: sends 2-byte Arduino commands.
    Each direction key = magnitude 1 (light). Hold FAST key = magnitude 3 (strong).
    Sends every 500ms. Exit with KEY_MANUAL_EXIT.
    """
    try:
        open_port()

        # Resolve key names to actual key strings from config
        channel_keys = []
        for attr in _MANUAL_CHANNEL_KEYS:
            channel_keys.append(getattr(Config.Keybinds, attr, None))
        fast_key = getattr(Config.Keybinds, 'MANUAL_FAST', 'f')

        prev_states = {k: False for k in channel_keys if k}
        prev_states[fast_key] = False
        last_send = time.time()

        while not proc.stop_event.is_set():
            with proc.manual_mode_lock:
                if not proc.manual_mode:
                    break
            if keyboard.is_pressed(Config.Keybinds.KEY_MANUAL_EXIT):
                proc.console.add_output(f"[MANUAL] tecla {Config.Keybinds.KEY_MANUAL_EXIT} PRESIONADA -> saliendo")
                break

            all_keys = list(set(k for k in channel_keys if k)) + [fast_key]
            curr_states = {k: keyboard.is_pressed(k) for k in all_keys}

            for k, curr in curr_states.items():
                if k in prev_states and curr != prev_states[k]:
                    estado = "PRESIONADA" if curr else "LIBERADA"
                    proc.console.add_output(f"[MANUAL] tecla {k.upper()} {estado}")
            prev_states = dict(curr_states)

            if time.time() - last_send >= 0.5:
                is_fast = curr_states.get(fast_key, False)
                mags = []
                for ck in channel_keys:
                    if ck and curr_states.get(ck, False):
                        mags.append(3 if is_fast else 1)
                    else:
                        mags.append(0)

                b1, b2 = encode_arduino_pair(
                    ccw=mags[0], cw=mags[1], up=mags[2],
                    down=mags[3], fwd=mags[4], bwd=mags[5],
                    left=mags[6] if len(mags) > 6 else 0,
                    right=mags[7] if len(mags) > 7 else 0
                )
                control.send(b1, b2)
                active = [_MANUAL_CHANNEL_KEYS[i].split('_',1)[1]
                          for i in range(len(mags)) if mags[i] > 0]
                label = ', '.join(active) if active else 'STOP'
                speed = 'FAST' if is_fast and active else ''
                proc.console.add_output(f"[MANUAL] {label} {speed}  b1={b1:06b} b2={b2:06b}")
                last_send = time.time()

            time.sleep(0.01)
            
    except serial.SerialException as e:
        proc.console.add_output(f"[MANUAL] Error de comunicación (serial): {e}")
    except Exception as e:
        proc.console.add_output(f"[MANUAL] Error inesperado: {e}")
    finally:
        close_port()    

    with proc.manual_mode_lock:
        proc.manual_mode = False
    proc.cmd_console.add_output("[MANUAL] modo manual finalizado")

# ==========================
#  MAIN
# ==========================
if __name__ == '__main__':
    # SOURCE_CONFIGS is defined at module level (single canonical location)

    # Solicitar modo LLM (ANTES de calibración)
    print("\nSelecciona el modelo de lenguaje (LLM):")
    print("1 - Local (Ollama) [default if installed]")
    print("2 - API Key (OpenAI Cloud)")
    llm_choice = input("Opcion [1-2] (Enter = auto): ").strip()

    if llm_choice == "1":
        configure_llm_mode("local")
    elif llm_choice == "2":
        configure_llm_mode("api")
    else:
        configure_llm_mode("auto")

    # Re-initialize client with the selected LLM settings
    reinit_llm_client()
    print("")

    # Solicitar tipo de calibración (ANTES de la fuente)
    print("Selecciona la calibración de cámara:")
    print("1 - Standard (calINSPIRO.npz) [default]")
    print("2 - PhCam (Samsung S24 Standard @ 2340x1080)")
    cal_choice = input("Opcion [1-2] (Enter = 1): ").strip()

    if cal_choice == "2":
        selected_cal_file = "calibration/calS24.npz"
        print(">> Usando calibración: PhCam (Samsung S24)")
    else:
        selected_cal_file = "calibration/calINSPIRO.npz"
        print(">> Usando calibración: Standard (calINSPIRO)")

    # Aplicar la calibración seleccionada a TODAS las configuraciones de fuente
    for key in SOURCE_CONFIGS:
        if "calibration" in SOURCE_CONFIGS[key]:
            SOURCE_CONFIGS[key]["calibration"] = selected_cal_file

    # Solicitar tipo de fuente
    print("\nSelecciona la fuente de video:")
    print("1 - Scrcpy (DJI Spark via Android - recommended)  [default]")
    print("2 - Phone Stream MJPEG (DJI Spark)")
    print("3 - Camara local (webcam)")
    print(f"4 - Stream HTTP ({CamIP})")
    print("5 - Especificar URL personalizada")
    
    source_choice = input("Opcion [1-5] (Enter = 1): ").strip()
    
    if source_choice == "2":
        # Phone Stream MJPEG
        print("\nDetecting phone hotspot IP...")
        gw_ip = detect_phone_gateway()
        if gw_ip:
            port = SOURCE_CONFIGS["phone_stream"]["port"]
            path = SOURCE_CONFIGS["phone_stream"]["path"]
            stream_url = f"http://{gw_ip}:{port}{path}"
            print(f"Phone IP: {gw_ip}")
            print(f"Stream URL: {stream_url}")
            src = stream_url
            source_type = "phone_stream"
        else:
            print("Could not detect phone IP.")
            manual_ip = input("Enter phone hotspot IP: ").strip()
            port = SOURCE_CONFIGS["phone_stream"]["port"]
            path = SOURCE_CONFIGS["phone_stream"]["path"]
            src = f"http://{manual_ip}:{port}{path}"
            source_type = "phone_stream"
    elif source_choice == "3":
        src = "0"
        source_type = "default"
    elif source_choice == "4":
        src = "stream"
        source_type = "stream"
    elif source_choice == "5":
        src = input("Introduce la URL del stream: ").strip()
        source_type = "stream"
    else:
        # Default: Scrcpy
        src = "scrcpy"
        source_type = "scrcpy"
    
    # Inicializar el procesador con el tipo de fuente
    proc = VideoProcessor(source_type=source_type)
    
    # Apply framerate mode from config
    framerate_mode = getattr(getattr(Config, 'Performance', None), 'FRAMERATE_MODE', 'auto')
    if framerate_mode == 'high':
        proc.detection_interval = 1
        proc.disable_auto_adjust = True
        proc.cmd_console.add_output("🚀 Modo FPS ALTO: detección cada frame (máximo rendimiento)")
    elif framerate_mode == 'medium':
        proc.detection_interval = 3
        proc.disable_auto_adjust = True
        proc.cmd_console.add_output("⚖️ Modo FPS MEDIO: detección cada 3 frames (balanceado)")
    elif framerate_mode == 'low':
        proc.detection_interval = 5
        proc.disable_auto_adjust = True
        proc.cmd_console.add_output("🐢 Modo FPS BAJO: detección cada 5 frames (ahorro de recursos)")
    else:  # 'auto'
        proc.disable_auto_adjust = False
        proc.cmd_console.add_output("🤖 Modo FPS AUTO: ajuste dinámico basado en rendimiento")
    
    proc.show_video_info = True  # Show detection info overlay
    
    # Optimización: Si solo usa pose (no ArUco), detección más frecuente (only in auto mode)
    if framerate_mode == 'auto' and not getattr(getattr(Config, 'AI', None), 'USE_ARUCO_MARKERS', False):
        proc.detection_interval = 2  # Más frecuente para pose-only
    
    # Cargar calibración solo si se usa ArUco (optimización de inicio)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cal_file = SOURCE_CONFIGS[source_type]["calibration"]
    cal_path = os.path.join(script_dir, cal_file)
    
    if proc.use_aruco:
        # Carga completa de calibración para ArUco
        if not os.path.exists(cal_path):
            proc.cmd_console.add_output(f"Advertencia: Archivo de calibración '{cal_file}' no encontrado")
            cal_path = os.path.join(script_dir, SOURCE_CONFIGS["default"]["calibration"])
            if not os.path.exists(cal_path):
                raise FileNotFoundError(f"Archivo de calibración por defecto '{cal_path}' no encontrado")
        
        try:
            data = np.load(cal_path)
            required_keys = ['K', 'D', 'width', 'height']
            if not all(key in data for key in required_keys):
                raise ValueError(f"Archivo de calibración incompleto. Se requieren: {required_keys}")
            
            proc.K = data['K']
            proc.D = data['D']
            proc.frame_width = int(data['width'])
            proc.frame_height = int(data['height'])
            
            # Validar datos de calibración
            if proc.K.shape != (3, 3) or proc.D.shape[0] < 4:
                raise ValueError("Formato de calibración inválido")
            if proc.frame_width <= 0 or proc.frame_height <= 0:
                raise ValueError("Dimensiones de frame inválidas")
            
            proc.calibration_loaded = True
                
        except Exception as e:
            raise RuntimeError(f"Error cargando calibración desde '{cal_path}': {e}")

        fx, fy = proc.K[0,0], proc.K[1,1]
        proc.fov_x, proc.fov_y = compute_fov(fx, fy, proc.frame_width, proc.frame_height)
    else:
        # Solo cargar dimensiones para pose-only (mucho más rápido)
        try:
            data = np.load(cal_path)
            proc.frame_width = int(data.get('width', 640))
            proc.frame_height = int(data.get('height', 480))
            # Use calibration FOV if K matrix is available (even in pose-only mode)
            if 'K' in data:
                K = data['K']
                fx, fy = K[0, 0], K[1, 1]
                proc.fov_x, proc.fov_y = compute_fov(fx, fy, proc.frame_width, proc.frame_height)
            else:
                proc.fov_x = 60.0
                proc.fov_y = 45.0
        except Exception:
            # Valores por defecto si falla
            proc.frame_width = 640
            proc.frame_height = 480
            proc.fov_x = 60.0
            proc.fov_y = 45.0
    
    # Add startup info to existing consoles (don't re-create — preserves init messages)
    if proc.use_aruco:
        proc.cmd_console.add_output(f"Usando calibración: {cal_file}")
    else:
        proc.cmd_console.add_output(f"⚡ Modo rápido: Pose-only (sin calibración ArUco)")
    proc.cmd_console.add_output(f"Horizontal FoV: {proc.fov_x:.2f}° | Vertical FoV: {proc.fov_y:.2f}°")
    proc.cmd_console.add_output(f"Intervalo de detección: {proc.detection_interval} frames")
    proc.cmd_console.add_output(f"FPS objetivo: {proc.target_fps}")

    # Crear adaptador de control según la fuente
    cfg = SOURCE_CONFIGS[source_type]
    control_mode = cfg.get("control", "serial")
    
    # Crear cola de frames (usar tamaño de config)
    frame_queue_size = getattr(getattr(Config, 'Performance', None), 'FRAME_QUEUE_SIZE', 2)
    
    control = ControlLink(
        mode=control_mode,
        serial_port=PUERTO,
        serial_baud=BAUD,
        serial_timeout=1,
        wifi_ip=CarIP,
        wifi_port=ESP_PORT,
        reconnect_grace=RECONNECT_GRACE
    )
    
    proc.cmd_console.add_output(f"Control: {control_mode.upper()} (2-byte Arduino protocol)")
    if control_mode == "serial":
        port_label = PUERTO if PUERTO.lower() != 'auto' else 'auto-detect'
        proc.cmd_console.add_output(f"   Puerto: {port_label} @ {BAUD} baud")
        proc.cmd_console.add_output(f"   Reconexion: {RECONNECT_GRACE}s grace")
    else:
        proc.cmd_console.add_output(f"   WiFi: {CarIP}:{ESP_PORT}")
    proc.cmd_console.add_output(f"📋 Cola de frames: {frame_queue_size}")
    proc.cmd_console.add_output("")
    proc.cmd_console.add_output("⌨️  CONTROLES:")
    proc.cmd_console.add_output(f"   TAB = Salir del programa")
    proc.cmd_console.add_output(f"   {Config.Keybinds.KEY_VOICE_RECORD} = Grabar comando de voz")
    proc.cmd_console.add_output(f"   {chr(Config.Keybinds.KEY_FACE_RECOGNITION)} = Reconocimiento facial")
    proc.cmd_console.add_output(f"   {Config.Keybinds.KEY_CANCEL_NAV} = EMERGENCY STOP (halts all movement)")
    proc.cmd_console.add_output(f"   6 = Toggle Modo Seguro (velocidad mínima)")
    proc.cmd_console.add_output(f"   {Config.Keybinds.KEY_MANUAL_TOGGLE} = Modo manual")
    proc.cmd_console.add_output(f"   8 = Toggle gesture recognition")
    proc.cmd_console.add_output(f"   9 = Find person (360° scan)")
    proc.cmd_console.add_output(f"   TTS: {'ON' if proc.tts_enabled else 'OFF (pyttsx3 not installed)'}")
    proc.cmd_console.add_output("")

    # ─── Auto-load face recognition (ArcFace via ONNX) ────────────────
    if FACE_RECOGNITION_AVAILABLE:
        try:
            db_dir = resolve_face_database_dir()
            proc.face_system = LiveFaceRecognition(database_dir=db_dir)
            auto_count = proc.face_system.auto_enroll_from_photos()
            proc.face_recognition_enabled = True
            people = proc.face_system.list_people()
            msg = f"👤 Face recognition ON — {len(people)} enrolled"
            if auto_count > 0:
                msg += f" (+{auto_count} from photos)"
            proc.cmd_console.add_output(msg)
            proc.cmd_console.add_output(f"   DB: {db_dir}")
            if people:
                proc.cmd_console.add_output(f"   Known: {', '.join(people)}")
        except Exception as e:
            proc.cmd_console.add_output(f"⚠️ Face recognition unavailable: {e}")
            proc.face_recognition_enabled = False
    proc.cmd_console.add_output("")

    frame_q = Queue(maxsize=frame_queue_size)

    # Crear e iniciar hilos
    threads = [
        threading.Thread(target=capture_thread, args=(src, frame_q, proc, source_type)),
        threading.Thread(target=processing_worker, args=(proc, frame_q)),
        threading.Thread(target=display_thread, args=(proc,)),
        threading.Thread(target=prompt_thread, args=(proc,)),
        threading.Thread(target=voice_input_thread, args=(proc,))
    ]

    for t in threads:
        t.daemon = True
        t.start()

    # Esperar a que los hilos terminen
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n⚠️ Interrupción por teclado (Ctrl+C), terminando...")
        proc.stop_event.set()

    # Dar tiempo para que los threads se enteren del stop
    print("\n🔄 Esperando que los threads terminen...")
    time.sleep(0.5)

    # Cerrar enlace de control (serial o wifi)
    try:
        close_port()
    except Exception as e:
        print(f"⚠️ Error cerrando puerto: {e}")

    # Stop TTS engine cleanly (avoids pyttsx3 DriverProxy.__del__ error)
    _tts_shutdown()

    # Esperar a que los hilos terminen (con timeout más corto)
    print("🧹 Limpiando recursos...")
    for i, t in enumerate(threads):
        t.join(timeout=0.5)
        if t.is_alive():
            print(f"⚠️ Thread {i} no terminó a tiempo")

    cv2.destroyAllWindows()
    print("✅ SIGO cerrado correctamente\n")
