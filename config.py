"""
Configuration file for SIGO ArUco Navigation System
Centralized settings for easy customization
"""
import os
import numpy as np

# ==========================
#  HARDWARE CONFIGURATION
# ==========================
class HardwareConfig:
    """Hardware connection settings"""
    # Serial port settings ('auto' = scan for Arduino automatically)
    SERIAL_PORT = 'auto'
    SERIAL_BAUD = 9600
    SERIAL_TIMEOUT = 1
    SERIAL_RECONNECT_GRACE = 15  # seconds to try reconnecting
    
    # WiFi settings
    CAMERA_IP = "192.168.165.106"
    VEHICLE_IP = "192.168.165.76"
    ESP_PORT = 5555

# ==========================
#  AI MODEL CONFIGURATION
# ==========================
class AIConfig:
    """AI model settings"""
    # OpenAI / Local LLM
    # To use Local LLM (Ollama), set OPENAI_BASE_URL="http://localhost:11434/v1" and OPENAI_MODEL="llama3.1"
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "ollama")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", None)  # None = use default OpenAI API
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TEMPERATURE = 0.1
    OPENAI_MAX_TOKENS = 10
    
    # Whisper
    WHISPER_MODEL_SIZE = "tiny"  # tiny, base, small, medium, large
    WHISPER_LANGUAGE = "es"
    WHISPER_SAMPLE_RATE = 16000
    WHISPER_DURATION = 4  # seconds
    
    # YOLO
    YOLO_MODEL = 'yolo11n.pt'  # YOLOv11 - 20% faster + more accurate
    YOLO_CONFIDENCE = 0.5
    
    # Pose estimation (PRIMARY distance method - replaces ArUco)
    USE_POSE_DISTANCE = True  # Enable pose-based distance estimation
    POSE_MODEL = 'yolov8s-pose.pt'  # YOLOv8 pose model
    USE_ARUCO_MARKERS = False  # Disable ArUco markers (using pose instead)
    
    # Face Recognition (ArcFace via ONNX Runtime — no DeepFace/TensorFlow needed)
    USE_FACE_RECOGNITION = True  # Enable facial recognition at startup
    FACE_DATABASE_DIR = 'face_database'  # Directory for enrolled face embeddings
    FACE_RECOGNITION_THRESHOLD = 0.35  # Cosine similarity threshold (0-1, lower = stricter)
    # Model: w600k_r50.onnx from InsightFace buffalo_l pack (~174MB, auto-downloaded)
    FACE_MODEL_PATH = os.path.expanduser('~/.insightface/models/buffalo_l/w600k_r50.onnx')
    
    # Focal length - auto-loaded from calibration file
    @staticmethod
    def get_focal_length(calibration_file=None):
        """Extract focal length from camera calibration file"""
        if calibration_file is None:
            # Build path relative to this config file
            config_dir = os.path.dirname(os.path.abspath(__file__))
            calibration_file = os.path.join(config_dir, 'calibration', 'calINSPIRO.npz')
        try:
            cal = np.load(calibration_file)
            K = cal['K']  # Camera matrix
            fx = K[0, 0]  # Focal length X
            fy = K[1, 1]  # Focal length Y
            return (fx + fy) / 2  # Average focal length
        except Exception as e:
            print(f"Warning: Could not load focal length from {calibration_file}: {e}")
            return None  # Return None so auto-estimation can kick in
    
    FOCAL_LENGTH_PIX = None  # Will be loaded automatically from calibration

# ==========================
#  NAVIGATION CONFIGURATION
# ==========================
class NavigationConfig:
    """Navigation and control settings"""
    # Target distances and thresholds
    DISTANCE_TARGET = 1.5  # meters - target approach distance (safety minimum)
    DISTANCE_CORRECTION = 1.0  # distance measurement correction factor
    ROTATION_THRESHOLD = 5  # degrees before rotating
    FAST_SPEED_THRESHOLD = 1.0  # meters - use fast speed beyond this
    
    # Timeouts
    MARKER_LOST_TIMEOUT = 3.0  # seconds before aborting navigation
    MARKER_EXPIRE_TIME = 2.0  # seconds before marker considered lost
    
    # Detection
    DETECTION_RADIUS_SCALE = 2.0  # radius around marker for object detection
    
    # Control loop timing
    NAVIGATION_UPDATE_RATE = 0.5  # seconds between navigation updates
    MANUAL_SEND_RATE = 0.5  # seconds between manual control sends

# ==========================
#  VISION CONFIGURATION
# ==========================
class VisionConfig:
    """Computer vision settings"""
    # ArUco marker
    ARUCO_MARKER_SIZE = 0.20  # meters (20cm)
    
    # ArUco detector parameters
    ARUCO_MIN_PERIMETER_RATE = 0.02
    ARUCO_ADAPTIVE_WIN_SIZE_MIN = 3
    ARUCO_ADAPTIVE_WIN_SIZE_MAX = 23
    ARUCO_ADAPTIVE_THRESH_CONSTANT = 7
    ARUCO_POLYGON_ACCURACY_RATE = 0.05
    
    # Tracking
    ROI_EXPANSION_SCALE = 1.2  # scale factor for ROI expansion
    SMOOTH_WINDOW_SIZE = 5  # frames for median smoothing
    
    # Image processing
    GAMMA_CORRECTION = 1.2  # gamma value for image enhancement
    
    # Marker validation
    MARKER_SIZE_TOLERANCE_SMALL = 0.4  # for markers with area < 50000
    MARKER_SIZE_TOLERANCE_LARGE = 0.2  # for markers with area >= 50000

# ==========================
#  VIDEO SOURCE CONFIGURATION
# ==========================
class SourceConfig:
    """Video source specific settings"""
    # Scrcpy capture resolution (set to your phone's resolution, or 0 for auto)
    SCRCPY_WIDTH = 2340
    SCRCPY_HEIGHT = 1080
    
    SOURCES = {
        "default": {
            "calibration": "calibration/calINSPIRO.npz",
            "detection_interval": 5,
            "target_fps": 30,
            "control": "wifi"
        },
        "scrcpy": {
            "calibration": "calibration/calINSPIRO.npz",
            "detection_interval": 5,
            "target_fps": 30,
            "control": "serial"
        },
        "smartview": {
            "calibration": "calibration/calINSPIRO.npz",
            "detection_interval": 3,
            "target_fps": 30,
            "control": "serial"
        },
        "phone_stream": {
            "calibration": "calibration/calINSPIRO.npz",
            "detection_interval": 2,
            "target_fps": 20,
            "port": 8080,
            "path": "/stream.mjpeg",
            "control": "serial"
        },
        "stream": {
            "calibration": "calibration/calINSPIRO.npz",
            "detection_interval": 1,
            "target_fps": 15,
            "control": "wifi",
        }
    }
    
    @classmethod
    def get_stream_url(cls, camera_ip=None):
        """Generate stream URL"""
        ip = camera_ip or HardwareConfig.CAMERA_IP
        return f"http://{ip}/stream"
    
    @classmethod
    def get_source_configs(cls,  camera_ip=None):
        """Return SOURCES dict with dynamic 'url' injected into stream entry."""
        configs = dict(cls.SOURCES)
        # Inject the stream URL (computed from current CAMERA_IP)
        stream = dict(configs.get("stream", {}))
        stream["url"] = cls.get_stream_url(camera_ip)
        configs["stream"] = stream
        return configs
    
    @classmethod
    def get_stream_url(cls, camera_ip=None):
        """Generate stream URL"""
        ip = camera_ip or HardwareConfig.CAMERA_IP
        return f"http://{ip}/stream"

# ==========================
#  UI CONFIGURATION
# ==========================
class UIConfig:
    """User interface settings"""
    # Display
    OUTPUT_WIDTH = 1280
    OUTPUT_HEIGHT = 720
    VIDEO_WIDTH_RATIO = 0.7
    CONSOLE_WIDTH_RATIO = 0.3
    INPUT_HEIGHT = 40
    
    # Console
    MAX_CONSOLE_LINES = 100
    MAX_COMMAND_HISTORY = 50
    CONSOLE_UPDATE_INTERVAL = 1.0  # seconds between detection info prints
    
    # Colors (BGR format)
    COLOR_MARKER = (0, 255, 0)  # Green
    COLOR_OBJECT = (255, 0, 0)  # Blue
    COLOR_GUIDE = (0, 0, 255)  # Red
    COLOR_TEXT = (0, 255, 255)  # Yellow
    
    # Font settings
    FONT = 'cv2.FONT_HERSHEY_SIMPLEX'
    FONT_SCALE = 0.5
    FONT_THICKNESS = 1

# ==========================
#  KEYBIND CONFIGURATION
# ==========================
class KeybindConfig:
    """Keyboard controls - easy to customize"""
    
    # Main window controls
    KEY_EXIT = 9  # TAB key (cv2.waitKey returns 9 for TAB)
    KEY_BACKSPACE = 8  # Backspace
    KEY_ENTER = 13  # Enter
    KEY_ARROW_PREFIX = [0, 224]  # Arrow key prefixes
    KEY_ARROW_UP = 72  # Up arrow (second byte)
    KEY_ARROW_DOWN = 80  # Down arrow (second byte)
    
    # Voice control
    KEY_VOICE_RECORD = '3'  # Hold to record voice
    
    # Navigation controls
    KEY_CANCEL_NAV = '5'  # Cancel active navigation
    KEY_SAFE_MODE = ord('6')  # Toggle safe speed mode
    
    # Feature toggles
    KEY_FACE_RECOGNITION = ord('4')  # Toggle face recognition
    KEY_GESTURE_MODE = ord('8')      # Toggle gesture recognition (F1)
    KEY_FIND_PERSON = ord('9')       # Find person by name (360° scan)
    
    # Mode switching
    KEY_MANUAL_TOGGLE = '7'  # Toggle manual control mode
    KEY_MANUAL_EXIT = '7'  # Exit manual mode
    
    # Manual control mapping (key: bit position)
    MANUAL_ROTATE_CCW = 'j'  # Rotate counter-clockwise - Bit 0
    MANUAL_ROTATE_CW = 'l'   # Rotate clockwise - Bit 1
    MANUAL_LEFT = 'i'        # Move left - Bit 2
    MANUAL_RIGHT = 'k'       # Move right - Bit 3
    MANUAL_FORWARD = 'u'     # Move forward - Bit 4
    MANUAL_BACK = 'o'        # Move back/takeoff - Bit 5
    MANUAL_RESERVED = 'p'    # Reserved - Bit 6
    MANUAL_FAST = 'f'        # Fast speed modifier - Bit 7
    
    # Manual control bit mapping (auto-generated from above)
    @staticmethod
    def get_manual_key_bits():
        """Returns dictionary mapping keys to bit positions"""
        return {
            KeybindConfig.MANUAL_ROTATE_CCW: 1 << 0,
            KeybindConfig.MANUAL_ROTATE_CW: 1 << 1,
            KeybindConfig.MANUAL_LEFT: 1 << 2,
            KeybindConfig.MANUAL_RIGHT: 1 << 3,
            KeybindConfig.MANUAL_FORWARD: 1 << 4,
            KeybindConfig.MANUAL_BACK: 1 << 5,
            KeybindConfig.MANUAL_RESERVED: 1 << 6,
            KeybindConfig.MANUAL_FAST: 1 << 7
        }

# ==========================
#  PERFORMANCE CONFIGURATION
# ==========================
class PerformanceConfig:
    """Performance tuning settings"""
    # Threading
    FRAME_QUEUE_SIZE = 1  # Minimal latency (1 = process latest frame only)
    THREAD_JOIN_TIMEOUT = 1.0
    
    # Framerate mode: 'auto', 'high', 'medium', 'low'
    # - 'auto': Adjusts detection interval based on actual FPS
    # - 'high': Maximum FPS (detection_interval=1, no auto-adjust)
    # - 'medium': Balanced FPS (detection_interval=3, no auto-adjust)
    # - 'low': Lower FPS (detection_interval=5, no auto-adjust)
    FRAMERATE_MODE = 'auto'  # 'auto', 'high', 'medium', 'low'
    
    # Auto-adjustment settings (only used if FRAMERATE_MODE='auto')
    FPS_LOW_THRESHOLD = 0.8  # 80% of target
    FPS_HIGH_THRESHOLD = 1.2  # 120% of target
    MIN_DETECTION_INTERVAL = 1
    MAX_DETECTION_INTERVAL = 10
    
    # Memory
    ENABLE_LAZY_LOADING = True  # Load AI models on first use
    
# ==========================
#  DEBUG CONFIGURATION
# ==========================
class DebugConfig:
    """Debug and logging settings"""
    SHOW_VIDEO_INFO = False  # Show detection info overlay on video
    SHOW_GUI = True  # Show GUI console
    VERBOSE_LOGGING = False  # Extra console output
    SHOW_FPS = True  # Display FPS counter

# ==========================
#  MAIN CONFIG CLASS
# ==========================
class Config:
    """Main configuration aggregator"""
    Hardware = HardwareConfig
    AI = AIConfig
    Navigation = NavigationConfig
    Vision = VisionConfig
    Source = SourceConfig
    UI = UIConfig
    Keybinds = KeybindConfig
    Performance = PerformanceConfig
    Debug = DebugConfig
