"""Download the two MediaPipe Tasks models track_reframe.py uses (Google's official model bucket)."""
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "models"   # reframe-track/models
MODELS = {
    "blaze_face_short_range.tflite":
        "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
    "efficientdet_lite0.tflite":
        "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/latest/efficientdet_lite0.tflite",
}

DEST.mkdir(exist_ok=True)
for name, url in MODELS.items():
    out = DEST / name
    if out.exists():
        print(f"have {out}")
        continue
    print(f"get  {url}")
    urllib.request.urlretrieve(url, out)
print("done")
