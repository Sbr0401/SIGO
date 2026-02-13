# Person-Centric Navigation Architecture

## Overview
SIGO has been refactored from ArUco marker-based navigation to person-centric pose-based navigation. The system now directly targets and tracks people instead of requiring them to be near markers.

## Architectural Changes

### 1. ID System
**Before (ArUco-centric):**
- Numeric IDs: `1`, `2`, `3` (marker IDs)
- User commands: "go to marker 3", "go to the person near marker 2"
- Navigation based on markers with associated objects

**After (Person-centric):**
- String IDs: `"person_1"`, `"person_2"`, `"person_3"`
- User commands: "go to person 1", "follow person 2"
- Direct person targeting without markers

### 2. Detection Storage
Both person and marker detections are stored in `self.history` with the same structure:

```python
self.history = {
    "person_1": {
        'corners': np.array([[x1,y1], [x2,y1], [x2,y2], [x1,y2]]),  # bbox as corners
        'distance': float,
        'angle_x': float,
        'angle_y': float,
        'prev_distance': float,
        'prev_angle_x': float,
        'prev_angle_y': float,
        'last_seen': timestamp,
        'draw_box': True,
        'last_detection_time': timestamp,
        'type': 'person',  # Differentiator
        'torso_state': 'full'|'partial'|'none',
        'keypoints': [[x,y,conf], ...],
        'bbox': (x1, y1, x2, y2)
    },
    42: {  # ArUco marker (if enabled)
        'corners': np.array([[x1,y1], ...]),
        'distance': float,
        'angle_x': float,
        'angle_y': float,
        # ... (traditional marker fields)
        'draw_box': True,
    }
}
```

### 3. Configuration Changes (`config.py`)
```python
# Pose detection enabled by default
USE_POSE_DISTANCE = True
FOCAL_LENGTH_PIX = 400.0  # For pose distance estimation

# ArUco markers disabled by default
USE_ARUCO_MARKERS = False
```

### 4. AI Integration
**Updated Prompt:**
```
Detected persons:
- Person 1 at 2.5m, angle 15°
- Person 2 at 3.2m, angle -10°

User can say: "go to person 1", "follow person 2"
Return person number (1, 2, 3) for navigation target.
```

**Response Parsing:**
- Positive number: Navigate to person (e.g., `1` → `"person_1"`)
- Negative number: Follow person (e.g., `-2` → `"-person_2"`)
- Handles both string IDs (`"person_1"`) and integers (ArUco `42`)

### 5. Navigation Loop
**Type-aware ID handling:**
```python
if isinstance(chosen_id, str):
    # Person ID: "person_1" or "-person_1" (follow)
    if chosen_id.startswith('-'):
        follow_mode = True
        chosen_id = chosen_id[1:]
    person_num = chosen_id.split('_')[1]
    target_label = f"Person {person_num}"
else:
    # ArUco marker ID: 42 or -42 (follow)
    if chosen_id < 0:
        follow_mode = True
        chosen_id = -chosen_id
    target_label = f"Marker {chosen_id}"
```

### 6. Rendering System
**Person rendering:**
- **Green box**: Full torso visible (all 4 keypoints: shoulders + hips)
- **Yellow box**: Partial torso visible (2-3 keypoints)
- **Gray box**: No torso visible (only bbox detection)
- Label: "Person 1", "Person 2", etc.
- Keypoints: Shoulders (5, 6) and hips (11, 12) drawn as circles

**ArUco rendering (if enabled):**
- Green polyline around corners
- Label: "ID: 42"

### 7. Distance Estimation Methods
**Pose-based (primary):**
1. Shoulder width measurement (most reliable)
2. Torso height measurement
3. Arm length measurement
4. Bounding box height estimation

**ArUco-based (legacy, optional):**
- solvePnP with known marker size

## User Commands
### Natural Language Examples
- "Go to person 1"
- "Navigate to person 2"
- "Follow person 3"
- "Person number 1"
- "Take me to the first person"

### Command Processing
1. Speech → Whisper transcription
2. Text → OpenAI API (with person list context)
3. API returns person number (1, 2, 3)
4. System converts to string ID ("person_1", "person_2", "person_3")
5. Navigation activates with target from history

## Benefits
1. **No marker dependency**: Track people directly
2. **Simpler user experience**: "person 1" vs "marker near person"
3. **More robust**: Pose detection works at longer distances
4. **Multiple tracking methods**: 4 fallback distance algorithms
5. **Clear visual feedback**: Color-coded torso visibility

## Backward Compatibility
ArUco markers can still be used if `USE_ARUCO_MARKERS = True` in config.py. Both systems work simultaneously:
- Person IDs: String format ("person_1")
- Marker IDs: Integer format (42)
- History stores both types
- Rendering handles both types
- Navigation supports both types

## Testing Checklist
- [x] Config: Pose enabled, ArUco disabled
- [x] Detection: People assigned person_1, person_2, person_3
- [x] Storage: History contains person entries with type='person'
- [x] AI: Understands "person 1", "person 2" commands
- [x] Parsing: Converts AI response (1) to string ID ("person_1")
- [x] Navigation: Handles string IDs in navigation loop
- [x] Rendering: Shows person boxes with keypoints, color-coded by torso
- [x] Labels: Displays "Person 1" not "ID: person_1"
- [ ] Live test: Run system, detect people, issue voice command
- [ ] Edge cases: Person leaves frame, multiple people, follow mode

## Files Modified
- `config.py`: USE_POSE_DISTANCE=True, USE_ARUCO_MARKERS=False
- `SIGO1.py`: 
  - Line 478-482: Added flags
  - Line 756-860: Refactored _detect_with_pose() 
  - Line 608-705: Made ArUco optional
  - Line 1070-1097: Updated info formatting
  - Line 1002-1063: Updated AI prompt & parsing
  - Line 1320-1357: Updated navigation loop
  - Line 890-920: Updated rendering
  - Removed duplicate pose rendering (lines 950-1000)

## Migration Notes
If you have existing code that uses marker IDs:
1. Check if ID is string: `isinstance(id, str)`
2. Person IDs start with "person_": `id.startswith('person_')`
3. Extract number: `person_num = id.split('_')[1]`
4. History structure is compatible for both types
