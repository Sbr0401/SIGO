"""
SIGO Face Recognition — ArcFace via ONNX Runtime
=================================================
Uses YOLOv8-pose keypoints for face localization (FREE — already computed),
ArcFace w600k_r50 for 512-dim embeddings via ONNX Runtime GPU.

No InsightFace Python package needed — direct ONNX inference.
"""
import cv2
import numpy as np
import os
import pickle
import time
import threading
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ─── ArcFace reference landmarks for 112×112 alignment ────────────────────
# Standard 3-point subset (left eye, right eye, nose) used for affine warp
ARCFACE_REF_3PT = np.array([
    [38.2946, 51.6963],   # left eye
    [73.5318, 51.5014],   # right eye
    [56.0252, 71.7366],   # nose tip
], dtype=np.float32)


# ─── Ensure CUDA / cuDNN DLLs from PyTorch are visible to ONNX Runtime ────
def _setup_cuda_dll_paths():
    """Add PyTorch's bundled CUDA 12 + cuDNN 9 DLLs to the DLL search path
    so ONNX Runtime can find them on Windows."""
    try:
        import torch
        torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
        if os.path.isdir(torch_lib):
            os.add_dll_directory(torch_lib)
    except Exception:
        pass

if os.name == 'nt':
    _setup_cuda_dll_paths()


# ─── ArcFace ONNX wrapper ─────────────────────────────────────────────────
class ArcFaceONNX:
    """ArcFace face recognition — loads w600k_r50.onnx, returns 512-dim embeddings."""

    def __init__(self, model_path: str = None):
        import onnxruntime as ort

        if model_path is None:
            model_path = os.path.expanduser(
                '~/.insightface/models/buffalo_l/w600k_r50.onnx'
            )
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"ArcFace model not found: {model_path}\n"
                f"  Download it with: pip install insightface && "
                f"python -c \"from insightface.app import FaceAnalysis; FaceAnalysis('buffalo_l')\"\n"
                f"  Or manually place w600k_r50.onnx in: {os.path.dirname(model_path)}"
            )

        # Prefer GPU, fallback to CPU
        providers = []
        if 'CUDAExecutionProvider' in ort.get_available_providers():
            providers.append('CUDAExecutionProvider')
        providers.append('CPUExecutionProvider')

        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        active = self.session.get_providers()
        print(f"[FaceRec] ArcFace loaded — provider: {active[0]}")

    def get_embedding(self, aligned_face: np.ndarray) -> np.ndarray:
        """Get 512-dim L2-normalised embedding from an aligned 112×112 face.

        Args:
            aligned_face: BGR image, already warped to 112×112
        Returns:
            512-dim unit-length embedding
        """
        img = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2RGB).astype(np.float32)
        img = (img / 127.5) - 1.0                      # normalise to [-1, 1]
        img = img.transpose(2, 0, 1)[np.newaxis, ...]   # HWC → 1×C×H×W

        embedding = self.session.run(
            [self.output_name], {self.input_name: img}
        )[0].flatten()

        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding /= norm
        return embedding

    @staticmethod
    def similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Cosine similarity (both are already L2-normalised)."""
        return float(np.dot(emb1, emb2))


# ─── Face alignment helper ────────────────────────────────────────────────
def align_face(
    frame: np.ndarray,
    left_eye: np.ndarray,
    right_eye: np.ndarray,
    nose: np.ndarray,
) -> Optional[np.ndarray]:
    """Warp a face to the ArcFace 112×112 template using 3-point affine.

    Args:
        frame:     Full BGR frame
        left_eye:  (x, y) array
        right_eye: (x, y) array
        nose:      (x, y) array
    Returns:
        Aligned 112×112 face, or *None* if the geometry is degenerate.
    """
    eye_dist = np.linalg.norm(left_eye - right_eye)
    if eye_dist < 5:
        return None

    src = np.array([left_eye, right_eye, nose], dtype=np.float32)
    M = cv2.getAffineTransform(src, ARCFACE_REF_3PT)
    return cv2.warpAffine(frame, M, (112, 112), borderValue=(0, 0, 0))


# ─── Pickle-based face database ───────────────────────────────────────────
class FaceDatabase:
    """Stores {name → list of 512-dim embeddings} on disk."""

    def __init__(self, database_dir: str = "face_database"):
        self.database_dir = Path(database_dir)
        self.db_file = self.database_dir / "face_db.pkl"
        self.database_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.people: Dict[str, dict] = {}
        self._load()

    # ── persistence ────────────────────────────────────────────────────
    def _load(self):
        if self.db_file.exists():
            try:
                with open(self.db_file, 'rb') as f:
                    data = pickle.load(f)
                # Validate structure: must be dict[str, dict with 'embeddings' list]
                if not isinstance(data, dict):
                    raise ValueError(f"Expected dict, got {type(data).__name__}")
                for name, entry in data.items():
                    if not isinstance(entry, dict) or 'embeddings' not in entry:
                        raise ValueError(f"Invalid entry for '{name}'")
                self.people = data
                print(f"[FaceDB] Loaded {len(self.people)} people "
                      f"({sum(len(v['embeddings']) for v in self.people.values())} embeddings)")
            except Exception as e:
                print(f"[FaceDB] Load error: {e}, starting fresh")
                # Keep corrupted file as backup for manual recovery
                bak = self.db_file.with_suffix('.pkl.corrupted')
                try:
                    import shutil
                    shutil.copy2(self.db_file, bak)
                    print(f"[FaceDB] Corrupted file saved as {bak}")
                except Exception:
                    pass
                self.people = {}
        else:
            print("[FaceDB] No existing database — starting fresh")

    def _save(self):
        try:
            # Atomic write: write to temp file, then rename (prevents corruption on crash)
            import tempfile
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(self.database_dir), suffix='.pkl.tmp'
            )
            try:
                with os.fdopen(tmp_fd, 'wb') as f:
                    pickle.dump(self.people, f)
                # Keep one backup of the previous good database
                if self.db_file.exists():
                    bak = self.db_file.with_suffix('.pkl.bak')
                    try:
                        import shutil
                        shutil.copy2(self.db_file, bak)
                    except Exception:
                        pass
                os.replace(tmp_path, self.db_file)
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                raise
        except Exception as e:
            print(f"[FaceDB] Save error: {e}")

    # ── add / remove / query ───────────────────────────────────────────
    def add_face(self, name: str, embedding: np.ndarray,
                 face_image: np.ndarray = None) -> bool:
        with self.lock:
            if name not in self.people:
                self.people[name] = {'embeddings': [], 'enrolled_at': time.time()}
            self.people[name]['embeddings'].append(embedding)

            if face_image is not None:
                img_dir = self.database_dir / name
                img_dir.mkdir(exist_ok=True)
                ts = int(time.time() * 1000)
                cv2.imwrite(str(img_dir / f"enrolled_{ts}.jpg"), face_image)

            self._save()
            return True

    def recognize(self, embedding: np.ndarray,
                  threshold: float = 0.35) -> Tuple[Optional[str], float]:
        best_name, best_sim = None, -1.0
        with self.lock:
            for name, data in self.people.items():
                embs = data['embeddings']
                if not embs:
                    continue
                # Vectorized dot product: (N, 512) @ (512,) → (N,) similarities
                sims = np.dot(np.array(embs), embedding)
                max_sim = float(sims.max())
                if max_sim > best_sim:
                    best_sim, best_name = max_sim, name
        if best_sim >= threshold:
            return best_name, best_sim
        return None, 0.0

    def remove_person(self, name: str) -> bool:
        with self.lock:
            if name in self.people:
                del self.people[name]
                self._save()
                img_dir = self.database_dir / name
                if img_dir.exists():
                    import shutil
                    shutil.rmtree(img_dir, ignore_errors=True)
                return True
        return False

    def rename_person(self, old_name: str, new_name: str) -> bool:
        """Rename a person in the database (embeddings + image folder)."""
        with self.lock:
            if old_name not in self.people:
                return False
            if new_name in self.people:
                # Merge into existing entry
                self.people[new_name]['embeddings'].extend(
                    self.people[old_name]['embeddings']
                )
            else:
                self.people[new_name] = self.people[old_name]
            del self.people[old_name]
            self._save()

        # Rename image folder if it exists
        old_dir = self.database_dir / old_name
        new_dir = self.database_dir / new_name
        if old_dir.exists():
            import shutil
            if new_dir.exists():
                # Move files into existing folder
                for f in old_dir.iterdir():
                    shutil.move(str(f), str(new_dir / f.name))
                shutil.rmtree(old_dir, ignore_errors=True)
            else:
                old_dir.rename(new_dir)
        return True

    def list_people(self) -> List[str]:
        with self.lock:
            return list(self.people.keys())


# ─── Main recognition system ──────────────────────────────────────────────
class LiveFaceRecognition:
    """Complete pipeline: pose-keypoints → ArcFace alignment → recognition.

    Face *detection* is free — we reuse the YOLOv8-pose keypoints
    (nose=0, left_eye=1, right_eye=2) that are already computed.
    Only the ArcFace embedding inference is extra work (~5-10 ms on GPU).
    """

    KP_NOSE      = 0
    KP_LEFT_EYE  = 1
    KP_RIGHT_EYE = 2

    def __init__(
        self,
        model_path: str = None,
        database_dir: str = "face_database",
        recognition_threshold: float = 0.35,
        min_eye_dist: float = 15.0,
        cooldown: float = 1.0,
        cache_ttl: float = 5.0,
    ):
        """
        Args:
            model_path:  Path to w600k_r50.onnx (None → default location)
            database_dir:  Where face_db.pkl lives
            recognition_threshold:  Cosine sim cutoff (0.3 = lenient, 0.5 = strict)
            min_eye_dist:  Skip faces smaller than this (pixels between eyes)
            cooldown:  Seconds between recognition attempts per person
            cache_ttl:  Seconds to trust a cached recognition result
        """
        self.arcface  = ArcFaceONNX(model_path)
        self.database = FaceDatabase(database_dir)
        self.threshold   = recognition_threshold
        self.min_eye_dist = min_eye_dist
        self.cooldown    = cooldown
        self.cache_ttl   = cache_ttl

        # Per-person recognition cache
        self._cache: Dict[str, Tuple[str, float, float]] = {}   # pid → (name, sim, ts)
        self._last_attempt: Dict[str, float] = {}               # pid → ts
        self._lock = threading.Lock()

    # ── face extraction from pose keypoints ────────────────────────────
    def extract_face(self, frame: np.ndarray,
                     keypoints: np.ndarray) -> Optional[np.ndarray]:
        """Crop & align a 112×112 face using YOLOv8-pose keypoints.

        Args:
            frame:     Full BGR frame
            keypoints: (17, 3) array — (x, y, confidence) per keypoint
        Returns:
            Aligned 112×112 face or *None*
        """
        if keypoints is None or len(keypoints) < 3:
            return None

        nose_c = keypoints[self.KP_NOSE][2]
        leye_c = keypoints[self.KP_LEFT_EYE][2]
        reye_c = keypoints[self.KP_RIGHT_EYE][2]

        if leye_c < 0.3 or reye_c < 0.3 or nose_c < 0.3:
            return None

        left_eye  = keypoints[self.KP_LEFT_EYE][:2].astype(np.float32)
        right_eye = keypoints[self.KP_RIGHT_EYE][:2].astype(np.float32)
        nose      = keypoints[self.KP_NOSE][:2].astype(np.float32)

        if np.linalg.norm(left_eye - right_eye) < self.min_eye_dist:
            return None

        return align_face(frame, left_eye, right_eye, nose)

    # ── recognition (with cache + cooldown) ────────────────────────────
    def recognize_person(self, frame: np.ndarray, keypoints: np.ndarray,
                         person_id: str) -> Tuple[Optional[str], float]:
        """Try to identify a tracked person.

        Returns (name, similarity) or (None, 0.0).
        Uses per-person cooldown and result caching to stay cheap.
        """
        if not self.database.people:
            return None, 0.0

        now = time.time()

        with self._lock:
            # return non-expired cache hit
            if person_id in self._cache:
                name, sim, ts = self._cache[person_id]
                if now - ts < self.cache_ttl:
                    return name, sim

            # respect cooldown
            last = self._last_attempt.get(person_id, 0)
            if now - last < self.cooldown:
                cached = self._cache.get(person_id)
                return (cached[0], cached[1]) if cached else (None, 0.0)
            self._last_attempt[person_id] = now

        aligned = self.extract_face(frame, keypoints)
        if aligned is None:
            return None, 0.0

        embedding = self.arcface.get_embedding(aligned)
        name, sim = self.database.recognize(embedding, self.threshold)

        # F2: Store embedding for re-identification after tracking loss
        if not hasattr(self, '_last_embeddings'):
            self._last_embeddings = {}
        self._last_embeddings[person_id] = embedding

        if name:
            with self._lock:
                self._cache[person_id] = (name, sim, now)
        return name, sim

    # ── F2 helpers for re-identification ───────────────────────────────
    def _extract_face_roi(self, frame: np.ndarray, keypoints: np.ndarray) -> 'np.ndarray | None':
        """Extract and align face ROI from keypoints (wrapper for re-ID)."""
        return self.extract_face(frame, keypoints)

    def _compute_embedding(self, aligned_face: np.ndarray) -> 'np.ndarray | None':
        """Compute ArcFace embedding from an already aligned face."""
        try:
            return self.arcface.get_embedding(aligned_face)
        except Exception:
            return None

    # ── live enrollment ────────────────────────────────────────────────
    def enroll_person(self, frame: np.ndarray, keypoints: np.ndarray,
                      name: str) -> Tuple[bool, str]:
        """Enroll a person's face from the current frame.

        Returns (success, message).
        """
        aligned = self.extract_face(frame, keypoints)
        if aligned is None:
            return False, "No se detectó cara. Asegúrate de que la persona esté mirando a la cámara."

        embedding = self.arcface.get_embedding(aligned)
        self.database.add_face(name, embedding, aligned)

        # invalidate caches so the new enrolment takes effect immediately
        with self._lock:
            self._cache.clear()
            self._last_attempt.clear()

        n = len(self.database.people[name]['embeddings'])
        return True, f"'{name}' guardado ({n} embedding{'s' if n > 1 else ''})"

    # ── utilities ──────────────────────────────────────────────────────
    def list_people(self) -> List[str]:
        return self.database.list_people()

    def remove_person(self, name: str) -> bool:
        ok = self.database.remove_person(name)
        if ok:
            with self._lock:
                self._cache.clear()
                self._last_attempt.clear()
        return ok

    def clear_cache(self, person_id: str = None):
        with self._lock:
            if person_id:
                self._cache.pop(person_id, None)
                self._last_attempt.pop(person_id, None)
            else:
                self._cache.clear()
                self._last_attempt.clear()

    # ── auto-enrollment from photos ────────────────────────────────────
    def auto_enroll_from_photos(self) -> int:
        """Batch-enroll faces from existing images in face_database/{Name}/.

        Scans each subdirectory of the database dir for .jpg/.png files.
        For each image, detects a face (using eye/nose keypoints via MediaPipe
        or simple frontal-face crop), computes ArcFace embedding, and adds it
        to the database — but only if not already enrolled from that file.

        Returns the number of NEW embeddings added.
        """
        import glob

        db_dir = self.database.database_dir
        added = 0

        for person_dir in sorted(db_dir.iterdir()):
            if not person_dir.is_dir():
                continue
            name = person_dir.name

            # Collect image files
            image_files = []
            for ext in ('*.jpg', '*.jpeg', '*.png', '*.bmp'):
                image_files.extend(person_dir.glob(ext))
            if not image_files:
                continue

            # Track already-enrolled filenames to avoid duplicates
            enrolled_key = f'_enrolled_files'
            with self.database.lock:
                if name not in self.database.people:
                    self.database.people[name] = {
                        'embeddings': [], 'enrolled_at': time.time()
                    }
                enrolled_set = set(
                    self.database.people[name].get(enrolled_key, [])
                )

            for img_path in sorted(image_files):
                fname = img_path.name
                if fname in enrolled_set:
                    continue  # already enrolled from this file

                img = cv2.imread(str(img_path))
                if img is None:
                    continue

                # Try to extract & align face from the photo
                aligned = self._extract_face_from_photo(img)
                if aligned is None:
                    print(f"[FaceDB] No face detected in {img_path.name}, skipping")
                    continue

                embedding = self.arcface.get_embedding(aligned)
                with self.database.lock:
                    self.database.people[name]['embeddings'].append(embedding)
                    files_list = self.database.people[name].setdefault(
                        enrolled_key, []
                    )
                    files_list.append(fname)
                added += 1

        if added > 0:
            self.database._save()
            self.clear_cache()
            print(f"[FaceDB] Auto-enrolled {added} new embedding(s) from photos")
        return added

    def _extract_face_from_photo(self, img: np.ndarray):
        """Extract and align a face from a standalone photo.
        Uses OpenCV's DNN face detector for robust detection, then aligns
        with eye landmarks for ArcFace input."""
        h, w = img.shape[:2]

        # Try OpenCV Haar cascade (ships with OpenCV, always available)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

        if len(faces) == 0:
            # Fallback: assume the entire image is a tightly-cropped face
            # Resize to 112x112 directly
            return cv2.resize(img, (112, 112))

        # Use largest face
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        face_roi = img[fy:fy+fh, fx:fx+fw]

        # Try to detect eyes for proper alignment
        eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_eye.xml'
        )
        eyes = eye_cascade.detectMultiScale(
            gray[fy:fy+fh, fx:fx+fw], 1.1, 5, minSize=(15, 15)
        )

        if len(eyes) >= 2:
            # Sort by x to get left/right eyes
            eyes = sorted(eyes, key=lambda e: e[0])
            ex1, ey1, ew1, eh1 = eyes[0]
            ex2, ey2, ew2, eh2 = eyes[1]
            left_eye = np.array([fx + ex1 + ew1/2, fy + ey1 + eh1/2], dtype=np.float32)
            right_eye = np.array([fx + ex2 + ew2/2, fy + ey2 + eh2/2], dtype=np.float32)
            nose = np.array([fx + fw/2, fy + fh * 0.65], dtype=np.float32)
            return align_face(img, left_eye, right_eye, nose)

        # No eyes found — just resize face ROI to 112x112
        return cv2.resize(face_roi, (112, 112))
