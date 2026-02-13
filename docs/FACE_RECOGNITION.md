# SIGO Facial Recognition System

## Overview
SIGO includes real-time facial recognition using **ArcFace** (w600k_r50) via direct ONNX Runtime inference. Faces are localized using YOLOv8-pose keypoints (eyes + nose) at **zero extra detection cost**, then warped to 112×112 and fed through ArcFace for 512-dimensional embeddings.

No InsightFace Python package, DeepFace, or TensorFlow is required.

## Features

### 1. **Live Enrollment via Console**
- Type `save person 1 as Juan` to register a face
- Confirmation prompt before saving (y/n)
- Multiple embeddings per person supported (just enroll again)
- Enrollment images saved to `face_database/{name}/`

### 2. **Automatic Real-time Recognition**
- Runs every frame on all visible persons (~10ms/face on GPU)
- Uses YOLOv8-pose keypoints for face localization (no separate face detector)
- Per-person recognition cache (5s TTL) + cooldown (1s) to avoid redundant inference
- Recognized persons show name + confidence in video overlay (pink label)

### 3. **Name-based Navigation**
- `go to Juan` / `follow Juan` — resolves name to person ID automatically
- Works with both text and voice commands
- Fast-path resolution before LLM (no extra latency)

### 4. **Face Removal**
- `remove Juan` / `delete Juan` — removes from database
- Case-insensitive matching

## Installation

### Required Package
```bash
pip install onnxruntime-gpu>=1.19.0
```

For CPU-only systems:
```bash
pip install onnxruntime>=1.19.0
```

### ArcFace Model
The model (`w600k_r50.onnx`, ~174MB) is downloaded automatically from the InsightFace buffalo_l model pack on first use. It's stored at:
```
~/.insightface/models/buffalo_l/w600k_r50.onnx
```

If automatic download fails, manually download from:
https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip

Extract so the ONNX files are in `~/.insightface/models/buffalo_l/`.

## Usage

### Enrolling Faces
In the SIGO console (bottom-right panel), type:
```
save person 1 as Juan
```

The system will ask for confirmation:
```
Save person_1 as 'Juan'? (y/n)
```

Type `y` to confirm. The face embedding is computed from the current frame and stored in the database.

**Tips for best enrollment:**
- Ensure the person is facing the camera
- Good lighting improves accuracy
- Enroll from multiple angles for better recognition (just run the command again)

### Recognizing Faces
No action needed — recognition runs automatically every frame. When a person is matched:
- Video overlay shows: `Juan 95% 1.2m` (instead of `P3 1.2m`)
- LLM prompt includes: `Name="Juan" (95%)`
- Label turns pink for identified persons

### Navigating by Name
```
go to Juan          → Navigate to the person identified as Juan
follow María        → Follow the person identified as María
find David          → Locate and navigate to David
```

Works with both text input and voice commands.

### Removing Faces
```
remove Juan         → Remove Juan from database
delete María        → Remove María from database
```

## Configuration

In `config.py`:
```python
class AIConfig:
    USE_FACE_RECOGNITION = True    # Enable at startup
    FACE_DATABASE_DIR = 'face_database'
    FACE_RECOGNITION_THRESHOLD = 0.35  # Cosine similarity (0-1, lower = stricter)
```

**Runtime Toggle:** Press **4** to toggle face recognition on/off.

## Database Structure

```
face_database/
├── face_db.pkl              # Pickle database (name → list of 512-dim embeddings)
├── Juan/
│   ├── enrolled_1707836400.jpg
│   └── enrolled_1707836500.jpg
└── María/
    └── enrolled_1707837200.jpg
```

## Technical Details

### Architecture
1. **Face Localization**: YOLOv8-pose keypoints (nose=KP0, left_eye=KP1, right_eye=KP2)
2. **Face Alignment**: 3-point affine warp to 112×112 using ArcFace reference landmarks
3. **Embedding**: ArcFace w600k_r50 ONNX → 512-dim L2-normalized vector
4. **Matching**: Cosine similarity against enrolled embeddings (threshold: 0.35)

### Performance
| Metric | GPU (RTX 5060) | CPU |
|--------|---------------|-----|
| ArcFace inference | ~10ms | ~88ms |
| First load (CUDA warmup) | ~2.3s | ~0.5s |
| Memory per embedding | ~2KB | ~2KB |

### CUDA Setup
ONNX Runtime automatically reuses CUDA 12 + cuDNN 9 DLLs bundled with PyTorch. No separate CUDA toolkit installation is needed for face recognition.

### Key Parameters (in `face_recognition_insightface.py`)
| Parameter | Default | Description |
|-----------|---------|-------------|
| Recognition threshold | 0.35 | Cosine similarity cutoff |
| Cache TTL | 5.0s | How long a recognition result is cached |
| Recognition cooldown | 1.0s | Min time between re-recognitions per person |
| Min eye distance | 15px | Minimum distance between eyes to attempt recognition |
| Keypoint confidence | 0.3 | Minimum confidence for face keypoints |

## Troubleshooting

### "ArcFace model not found"
Download the buffalo_l model pack:
```bash
# The model auto-downloads, but if it fails:
# 1. Download: https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip
# 2. Extract to: ~/.insightface/models/buffalo_l/
# 3. Ensure w600k_r50.onnx exists in that directory
```

### "CUDA provider failed, using CPU"
- Ensure PyTorch with CUDA is installed (provides the CUDA/cuDNN DLLs)
- For RTX 50-series: `pip install --pre torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu128`
- Face recognition still works on CPU (~88ms vs ~10ms)

### Recognition accuracy is low
- Enroll the person again from a different angle
- Ensure good lighting during enrollment
- Lower threshold in config (e.g., 0.30) for stricter matching
- Make sure the person is facing the camera

### Person not being recognized after track ID change
- This is normal — ByteTrack may assign a new ID when a person is re-detected
- The system re-identifies them within 1-2 frames (~30ms) when their face is visible
- If their face isn't visible (turned away), they stay as P# until face is seen again

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `4` | Toggle face recognition on/off |
| `3` (hold) | Record voice command |
| `5` | Cancel navigation |
| `TAB` | Exit SIGO |
