# SIGO - Sistema Inteligente de Guiado y Orientación

**AI-Powered ArUco Marker Navigation System v2.0**

Control your robot/vehicle using natural language commands and computer vision tracking.

## 🎯 Features

- 🎥 **Multi-source video**: Local webcam, Android (scrcpy), or IP camera stream
- 🔍 **Person tracking**: YOLOv8-Pose with distance estimation from body keypoints
- 👤 **Facial recognition**: Identify people from stored database (NEW!)
- 🔍 **ArUco marker tracking**: 3D position estimation with sub-meter accuracy (legacy)
- 🤖 **AI object detection**: YOLO v11 for identifying people, vehicles, objects
- 🗣️ **Voice control**: Spanish voice commands via Whisper AI
- 🧠 **Natural language**: GPT-4 interprets "go to John" or "follow María"
- 🎮 **Manual control**: Direct keyboard control for testing
- 📊 **Real-time GUI**: Split-screen video + console interface
- 🔌 **Dual connectivity**: Serial (RS232) or WiFi control

## 🚀 Quick Start

### Prerequisites
```bash
# Activate virtual environment
.venv\Scripts\activate

# All dependencies should be installed
# If not: pip install -r requirements.txt
```

### Run
```bash
python SIGO1.py
```

### First-Time Setup
1. Select video source (1-4)
2. Wait for AI models to load (only first run)
3. Place ArUco markers in view
4. Give voice or text commands!

## 🎮 Controls

### Keyboard Controls

**Navigation Mode:**
- `Enter` - Send text command
- `↑/↓` - Navigate command history
- `Backspace` - Edit command
- `5` - Cancel current navigation
- `4` - Toggle face recognition
- `TAB` - Exit program

**Manual Mode:**
- `7` - Toggle manual control
- `J` - Rotate left
- `L` - Rotate right
- `I` - Move up
- `K` - Move down
- `U` - Move forward
- `O` - Move backward
- `F` - Fast speed mode
- `7` again - Exit manual mode

**Voice Control:**
- `3` (hold) - Record 4-second voice command

## 💬 Command Examples

### Text Commands (type in console):
```
> go to person 1
> follow John
> find María
> go to marker 3
> approach the car
> sigue a David (follow David)
```

### Voice Commands (press 3):
- "Ve a la persona uno"
- "Sigue a John"
- "Busca a María"
- "Acércate a David"

## 👤 Face Recognition (NEW!)

SIGO can now identify people from a stored database:

1. **Setup database:**
   ```bash
   python manage_faces.py
   ```
   Add 3-5 photos per person for best results

2. **Enable recognition:**
   - Set `Config.AI.USE_FACE_RECOGNITION = True` in config.py
   - Or press `R` during runtime to toggle

3. **Use with commands:**
   ```
   > go to John          # Navigate to person identified as John
   > follow María        # Follow María
   ```

See [FACE_RECOGNITION.md](FACE_RECOGNITION.md) for detailed guide.

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Hardware
Config.Hardware.SERIAL_PORT = 'COM8'
Config.Hardware.VEHICLE_IP = "192.168.165.76"

# Navigation
Config.Navigation.DISTANCE_TARGET = 0.3  # meters
Config.Navigation.ROTATION_THRESHOLD = 5  # degrees

# AI Models
Config.AI.WHISPER_MODEL_SIZE = "tiny"  # tiny/base/small
Config.AI.YOLO_MODEL = 'yolo11n.pt'
Config.AI.USE_FACE_RECOGNITION = False  # Enable facial recognition

# UI
Config.Debug.SHOW_VIDEO_INFO = True  # Show overlays
```

## 📁 Required Files

```
SIGO/
├── SIGO1.py           # Main program
├── config.py          # Configuration
├── CalSpark.npz       # Camera calibration (webcam/scrcpy)
├── Cals3.npz          # Camera calibration (IP stream)
└── yolov8n.pt         # YOLO model (auto-downloaded)
```

## 🔧 Troubleshooting

### "Calibration file not found"
- Place `.npz` files in same folder as SIGO1.py
- Check `SOURCE_CONFIGS` in config.py for correct filename

### "Could not open serial port"
- Verify COM port in Device Manager
- Check `Config.Hardware.SERIAL_PORT`
- Try different baud rate

### "Connection lost" during WiFi control
- Verify ESP32 is powered and connected
- Ping `Config.Hardware.VEHICLE_IP`
- Check firewall settings

### Models loading slowly
- Normal on first run (~10-30 seconds)
- Subsequent runs are fast (lazy loading)
- GPU recommended for Whisper/YOLO

### No markers detected
- Ensure good lighting
- Use 4x4 ArUco markers (DICT_4X4_50)
- Markers should be ~20cm size
- Camera must be calibrated

## 📊 Performance Tips

1. **Adjust detection interval**: Lower = more accurate, higher = faster FPS
2. **Use GPU**: CUDA significantly speeds up YOLO and Whisper
3. **Reduce video resolution**: Edit calibration or use lower res stream
4. **Disable video overlays**: Set `Config.Debug.SHOW_VIDEO_INFO = False`

## 🐛 Debug Mode

Enable verbose logging:
```python
Config.Debug.VERBOSE_LOGGING = True
Config.Debug.SHOW_VIDEO_INFO = True
Config.Debug.SHOW_FPS = True
```

## 🔐 Security Notes

- OpenAI API key required: Set `OPENAI_API_KEY` environment variable
- WiFi control sends unencrypted bytes - use on trusted networks
- No authentication on control connection

## 📖 How It Works

1. **Video Capture** → Undistort → Gamma correction
2. **ArUco Detection** → 3D pose estimation → Distance/angle
3. **Object Detection** → YOLO identifies objects near markers
4. **AI Processing** → GPT-4 matches user command to marker
5. **Navigation** → Calculate rotation/speed → Send control byte
6. **Tracking** → MOSSE tracker maintains lock when occluded

## 🤝 Contributing

This is a personal project, but improvements welcome:
- Bug reports via issues
- Feature requests
- Code optimization PRs

## 📄 License

Personal use project - no formal license

## 🙏 Acknowledgments

- **OpenAI** - GPT-4 and Whisper models
- **Ultralytics** - YOLO v8 object detection
- **OpenCV** - Computer vision framework
- **ArUco** - Marker detection system

---

**Author**: Yosef  
**Version**: 2.0  
**Last Updated**: November 2025  

For detailed improvements, see `IMPROVEMENTS.md`
