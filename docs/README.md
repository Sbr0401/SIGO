# SIGO - Sistema Inteligente de Guiado y Orientación

**AI-Powered Person Tracking & Navigation System v2.0**

Control your robot/vehicle using natural language commands, voice, and computer vision tracking.

## 🎯 Features

- 🎥 **Multi-source video**: Local webcam, Android (scrcpy), Smart View/Miracast, MJPEG stream, or IP camera
- 🔍 **Person tracking**: YOLOv8-Pose with distance estimation from body keypoints (primary mode)
- 👤 **Facial recognition**: ArcFace via ONNX Runtime — identify enrolled people in real-time
- 🤖 **AI object detection**: YOLOv11 for identifying people, vehicles, objects
- 🗣️ **Voice control**: Spanish voice commands via faster-whisper
- 🧠 **Natural language**: GPT-4 / Ollama (local LLM) interprets commands like "go to John"
- 🎮 **Manual control**: Direct keyboard control for testing
- 📊 **Real-time GUI**: Split-screen video + console interface
- 🔌 **Dual connectivity**: Serial (RS232) or WiFi (ESP32) control
- 🔍 **ArUco markers**: Legacy 3D pose estimation (optional, disabled by default)

## 🚀 Quick Start

### Prerequisites
- Python 3.12 (recommended)
- Windows 10/11
- NVIDIA GPU (RTX series recommended) or CPU
- Webcam or Android phone with USB debugging
- Ollama (free local LLM) **or** OpenAI API key

### Installation

**Option A — Automatic (recommended):**
Double-click `setup_sigo.bat` and select "Instalación Completa" (option 1).

**Option B — Manual:**
```bash
cd SIGO-FINAL
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements\requirements.txt

# Optional: Face recognition (ArcFace via ONNX Runtime GPU)
pip install -r requirements\requirements-face.txt
```

### Run
```bash
python SIGO1.py
```

On first run, YOLO models are downloaded automatically by Ultralytics (~6MB for yolo11n, ~23MB for yolov8s-pose).

### First-Time Setup
1. Select LLM mode (Ollama local or OpenAI API)
2. Select calibration file
3. Select video source (scrcpy, webcam, stream, etc.)
4. Wait for AI models to load (only first run)
5. Give voice or text commands!

## 🎮 Controls

### Keyboard Controls

**Navigation Mode:**
- `Enter` — Send text command
- `↑/↓` — Navigate command history
- `Backspace` — Edit command
- `3` (hold) — Record 4-second voice command
- `4` — Toggle face recognition
- `5` — Cancel current navigation
- `6` — Toggle safe speed mode
- `7` — Toggle manual control mode
- `8` — Toggle gesture recognition
- `TAB` — Exit program

**Manual Mode (press `7` to enter/exit):**
- `J` — Rotate counter-clockwise (Bit 0)
- `L` — Rotate clockwise (Bit 1)
- `I` — Left (Bit 2)
- `K` — Right (Bit 3)
- `U` — Forward (Bit 4)
- `O` — Backward (Bit 5)
- `F` — Fast speed modifier (Bit 7)

See [KEYBINDS.md](KEYBINDS.md) for the full list.

## 💬 Command Examples

### Text Commands (type in console):
```
> go to person 1          — Navigate to detected person #1
> follow John             — Follow person identified as "John"
> find María              — Search for María
> save person 1 as Juan   — Enroll person 1's face as "Juan"
> remove Juan             — Delete Juan from face database
> sigue a David           — Follow David (Spanish)
```

### Voice Commands (hold `3`):
- "Ve a la persona uno"
- "Sigue a John"
- "Busca a María"
- "Acércate a David"

## 👤 Face Recognition

SIGO identifies people using ArcFace embeddings via ONNX Runtime (no TensorFlow/DeepFace needed).

1. **Enroll faces** via the in-app console during runtime:
   ```
   save person 1 as Juan       — Register person 1 as "Juan"
   remove Juan                  — Remove Juan from database
   ```

2. **Enable/disable** at runtime:
   - Press `4` to toggle face recognition on/off
   - Or set `Config.AI.USE_FACE_RECOGNITION = True/False` in `config.py`

3. **Navigate to a person**:
   ```
   go to Juan                   — Navigate to the person identified as Juan
   ```

The ArcFace model (`w600k_r50.onnx`) is downloaded automatically on first use (~174MB).
See [FACE_RECOGNITION.md](FACE_RECOGNITION.md) for details.

## ⚙️ Configuration

Edit `config.py` to customize. Key settings:

```python
# Hardware — Serial auto-detects Arduino; IPs need your network
Config.Hardware.SERIAL_PORT = 'auto'           # 'auto' scans for Arduino
Config.Hardware.CAMERA_IP = "192.168.x.x"      # Your phone/camera IP
Config.Hardware.VEHICLE_IP = "192.168.x.x"     # Your ESP32 IP

# Navigation
Config.Navigation.DISTANCE_TARGET = 1.5        # meters — safety distance
Config.Navigation.ROTATION_THRESHOLD = 5       # degrees before rotating

# AI Models
Config.AI.WHISPER_MODEL_SIZE = "tiny"           # tiny/base/small/medium
Config.AI.YOLO_MODEL = 'yolo11n.pt'             # Auto-downloaded by Ultralytics
Config.AI.USE_FACE_RECOGNITION = True           # Enable facial recognition
Config.AI.USE_POSE_DISTANCE = True              # Pose-based distance (primary)
Config.AI.USE_ARUCO_MARKERS = False             # ArUco markers (legacy)

# Video source resolution (match your phone)
Config.Source.SCRCPY_WIDTH = 2340
Config.Source.SCRCPY_HEIGHT = 1080

# LLM (environment variables or config)
# For Ollama: OPENAI_API_KEY=ollama, OPENAI_BASE_URL=http://localhost:11434/v1
# For OpenAI: OPENAI_API_KEY=sk-your-key
```

See `.env.example` for environment variable templates.

## 📁 Project Structure

```
SIGO-FINAL/
├── SIGO1.py                         # Main application
├── config.py                        # Centralized configuration
├── face_recognition_insightface.py  # ArcFace face recognition engine
├── yolov8s-pose.pt                  # YOLOv8 pose model (ships with repo)
├── setup_sigo.bat                   # Automated installer (menu-driven)
├── run_sigo_local.bat               # Launcher with Ollama (local LLM)
├── .env.example                     # Environment variable template
│
├── calibration/
│   ├── calINSPIRO.npz               # Camera calibration (standard)
│   └── calS24.npz                   # Camera calibration (Samsung S24)
│
├── requirements/
│   ├── requirements.txt             # Main dependencies
│   ├── requirements-cpu.txt         # CPU-only variant
│   ├── requirements-face.txt        # Face recognition (onnxruntime-gpu)
│   └── requirements-performance.txt # Performance optimizations
│
├── face_database/                   # Enrolled face embeddings (starts empty)
│
└── docs/
    ├── README.md                    # This file
    ├── KEYBINDS.md                  # Keyboard shortcuts
    ├── INSTALLATION.md              # Installation guide
    ├── FACE_RECOGNITION.md          # Face recognition guide
    └── ...
```

## 🔧 Troubleshooting

### "Calibration file not found"
- Calibration files ship in `calibration/` — select the right one at startup
- Create your own with `calibrate_distance.py`

### "Could not open serial port"
- Set `Config.Hardware.SERIAL_PORT = 'auto'` (default) to auto-scan
- Or check Device Manager for the correct COM port

### "Connection lost" during WiFi control
- Verify ESP32 is powered and on the same network
- Ping `Config.Hardware.VEHICLE_IP`
- Check firewall settings

### Face recognition not working
- Install: `pip install -r requirements\requirements-face.txt`
- The ArcFace model downloads automatically on first run
- Enroll faces with `save person 1 as Name` in the console

### Models loading slowly
- Normal on first run (downloads + compilation)
- Subsequent runs are fast (lazy loading + caching)
- NVIDIA GPU recommended for Whisper/YOLO

## 📊 Performance Tips

1. **Use GPU**: CUDA significantly speeds up YOLO and Whisper
2. **Framerate mode**: Set `Config.Performance.FRAMERATE_MODE` to `'high'`, `'medium'`, `'low'`, or `'auto'`
3. **Disable overlays**: `Config.Debug.SHOW_VIDEO_INFO = False`
4. **Install Numba**: `pip install numba` for 10-100x faster angle calculations

## 📖 How It Works

1. **Video Capture** → Undistort → Gamma correction
2. **Pose Detection** → YOLOv8-Pose keypoints → Distance estimation from body proportions
3. **Object Detection** → YOLOv11 identifies people, vehicles, objects
4. **Face Recognition** → ArcFace embeddings match detected faces to enrolled database
5. **AI Processing** → GPT-4/Ollama matches user command to detected target
6. **Navigation** → Calculate rotation/speed → Send 2-byte control packet
7. **Tracking** → ByteTrack maintains identity across frames

---

**Author**: Yosef
**Version**: 2.0
**Last Updated**: February 2026

For detailed improvements, see [IMPROVEMENTS.md](IMPROVEMENTS.md)
