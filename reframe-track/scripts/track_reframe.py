"""Subject-tracking reframe: 16:9 (or any landscape) -> 9:16 with a crop window that follows a face or person.

Layer 2 of the smart-reframe pair. Layer 1 (reframe-eye/SKILL.md) decides per shot whether to track,
hold a fixed crop, or fall back to a blurred background; this script tracks, and with --plan renders
those per-shot decisions in a single pass (no cut + join, so lips stay in sync).

  python track_reframe.py in.mp4 -o out_916.mp4                  # auto: face first, person as fallback
  python track_reframe.py in.mp4 --plan-only -o plan.json         # trajectory + per-shot report, no render
  python track_reframe.py in.mp4 -o out.mp4 --plan plan.json      # per-shot crop / track / blur from reframe-eye
  python track_reframe.py in.mp4 -o out.mp4 --debug debug.mp4     # also write a source-size video with boxes

Runs fully local: MediaPipe Tasks models in ../models, ffmpeg on PATH. Nothing is uploaded.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

HERE = Path(__file__).resolve().parent
MODELS = Path(os.environ.get("REFRAME_MODELS", HERE.parent / "models"))


# ---------- detection ----------

class Detector:
    def __init__(self, subject: str):
        self.subject = subject
        self.face = None
        self.person = None
        if subject in ("auto", "face"):
            opts = vision.FaceDetectorOptions(
                base_options=mp_tasks.BaseOptions(model_asset_path=str(MODELS / "blaze_face_short_range.tflite")),
                min_detection_confidence=0.5)
            self.face = vision.FaceDetector.create_from_options(opts)
        if subject in ("auto", "person"):
            opts = vision.ObjectDetectorOptions(
                base_options=mp_tasks.BaseOptions(model_asset_path=str(MODELS / "efficientdet_lite0.tflite")),
                category_allowlist=["person"], score_threshold=0.4, max_results=5)
            self.person = vision.ObjectDetector.create_from_options(opts)

    def detect(self, bgr: np.ndarray) -> list[dict]:
        """Return candidate boxes in source pixels: {x,y,w,h,score,kind,cx}. cx is the horizontal anchor."""
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        out: list[dict] = []
        if self.face is not None:
            # short-range model is trained on near faces; run it on the full frame and on a 2x upscale
            # of the frame so small faces in wide shots still register.
            for scale in (1.0, 2.0):
                img = image if scale == 1.0 else mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR))
                for d in self.face.detect(img).detections:
                    b = d.bounding_box
                    x, y, w, h = b.origin_x / scale, b.origin_y / scale, b.width / scale, b.height / scale
                    out.append(dict(x=x, y=y, w=w, h=h, score=d.categories[0].score, kind="face", cx=x + w / 2))
                if out:
                    break
        if not out and self.person is not None:
            for d in self.person.detect(image).detections:
                b = d.bounding_box
                # anchor on the head region: centre of the top quarter of the body box
                out.append(dict(x=b.origin_x, y=b.origin_y, w=b.width, h=b.height,
                                score=d.categories[0].score, kind="person", cx=b.origin_x + b.width / 2))
        return out


def pick(cands: list[dict], prev_cx: float | None) -> dict | None:
    if not cands:
        return None
    if prev_cx is None:
        return max(cands, key=lambda c: c["w"] * c["h"] * c["score"])
    # continuity: prefer the candidate near the previous subject, weighted by size
    return max(cands, key=lambda c: c["w"] * c["h"] * c["score"] / (1 + abs(c["cx"] - prev_cx) / 100))


# ---------- scenes ----------

def scene_cuts(path: str, threshold: float) -> list[float]:
    """Shot boundaries from ffmpeg scdet (same detector ffmpeg-skill's scenes.py uses)."""
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-i", path, "-an",
           "-vf", f"scdet=threshold={threshold}", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [float(m) for m in re.findall(r"lavfi\.scd\.time:\s*([0-9.]+)", r.stderr)]


# ---------- smoothing ----------

def gaussian_smooth(xs: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0 or len(xs) < 3:
        return xs
    radius = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    k /= k.sum()
    padded = np.pad(xs, radius, mode="edge")
    return np.convolve(padded, k, mode="valid")


def deadzone(xs: np.ndarray, zone: float) -> np.ndarray:
    """Hold the camera still while the subject wobbles inside +-zone px; follow only real moves."""
    if zone <= 0:
        return xs
    out = xs.copy()
    cur = xs[0]
    for i, x in enumerate(xs):
        if x > cur + zone:
            cur = x - zone
        elif x < cur - zone:
            cur = x + zone
        out[i] = cur
    return out


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True, help="output .mp4 (or .json with --plan-only)")
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--subject", choices=["auto", "face", "person"], default="auto")
    ap.add_argument("--sample-fps", type=float, default=10.0, help="detection rate (default 10/s)")
    ap.add_argument("--smooth", type=float, default=0.6, help="smoothing window in seconds (gaussian sigma)")
    ap.add_argument("--deadzone", type=float, default=0.06, help="still zone as a fraction of crop width")
    ap.add_argument("--lead", type=float, default=0.0,
                    help="look-room: shift the frame toward where the subject is heading, fraction of crop width")
    ap.add_argument("--scene-threshold", type=float, default=10.0)
    ap.add_argument("--min-hit", type=float, default=0.3,
                    help="a shot whose detection rate is below this is marked 'blur' instead of 'track'")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--plan", help="JSON from reframe-eye: {shots:[{start,end,mode:crop|track|blur,crop_x}]}; "
                    "renders exactly these decisions in one pass")
    ap.add_argument("--plan-only", action="store_true", help="analyse only and write the per-shot report as JSON")
    ap.add_argument("--debug", help="write a source-size preview with detections and the crop window")
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.input)
    if not cap.isOpened():
        print(f"cannot open {a.input}", file=sys.stderr)
        return 2
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    aw, ah = (float(v) for v in a.aspect.split(":"))
    cw = int(round(H * aw / ah / 2) * 2)
    if cw >= W:
        print("source is already as narrow as the target aspect; nothing to track", file=sys.stderr)
        return 2
    max_x = W - cw

    given = None
    if a.plan:
        given = json.loads(Path(a.plan).read_text(encoding="utf-8"))["shots"]
        bounds = sorted({0, n} | {min(n, int(round(float(sh["start"]) * fps))) for sh in given})
    else:
        cuts = scene_cuts(a.input, a.scene_threshold)
        bounds = sorted({0, n} | {min(n, int(round(t * fps))) for t in cuts})
    shots = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1) if bounds[i + 1] > bounds[i]]

    def given_for(s: int) -> dict | None:
        if given is None:
            return None
        t = s / fps
        return min(given, key=lambda sh: abs(float(sh["start"]) - t))

    need_detect = [given is None or given_for(s).get("mode") == "track" for s, _ in shots]
    det = Detector(a.subject) if any(need_detect) else None
    step = max(1, int(round(fps / a.sample_fps)))
    raw = np.full(n, np.nan)
    kinds: dict[int, str] = {}
    boxes: dict[int, dict] = {}
    prev = None
    shot_of = np.zeros(n, dtype=int)
    for si, (s, e) in enumerate(shots):
        shot_of[s:e] = si
    i = 0
    cur_shot = -1
    while det is not None:
        ok, frame = cap.read()
        if not ok or i >= n:
            break
        if shot_of[i] != cur_shot:
            cur_shot = shot_of[i]
            prev = None  # new shot: forget the previous subject
        if need_detect[shot_of[i]] and (i % step == 0 or (i > 0 and shot_of[i] != shot_of[i - 1])):
            c = pick(det.detect(frame), prev)
            if c:
                raw[i] = c["cx"]
                kinds[i] = c["kind"]
                boxes[i] = c
                prev = c["cx"]
        i += 1
    cap.release()
    if det is not None:
        n = i  # trust what was actually decoded
        raw = raw[:n]
        shots = [(s, min(e, n)) for s, e in shots if s < n]

    xs = np.zeros(n)
    report = []
    sample_idx = np.array(sorted(set(range(0, n, step)) | {s for s, _ in shots}))
    for si, (s, e) in enumerate(shots):
        g = given_for(s)
        idx = sample_idx[(sample_idx >= s) & (sample_idx < e)]
        hits = idx[~np.isnan(raw[idx])]
        rate = len(hits) / max(1, len(idx))
        kind_counts: dict[str, int] = {}
        for h in hits:
            kind_counts[kinds[int(h)]] = kind_counts.get(kinds[int(h)], 0) + 1
        if g is not None and g.get("mode") in ("crop", "blur"):
            mode = g["mode"]
            x = np.full(e - s, float(g.get("crop_x", 0.5)) * max_x)
        else:
            if len(hits) == 0:
                centre = np.full(e - s, W / 2)
            else:
                centre = np.interp(np.arange(s, e), hits, raw[hits])  # holds the ends flat
            path = gaussian_smooth(deadzone(centre, a.deadzone * cw), a.smooth * fps)
            if a.lead:
                vel = np.gradient(path)
                path = path + np.sign(vel) * np.minimum(np.abs(vel) * fps, 1) * a.lead * cw
            x = np.clip(path - cw / 2, 0, max_x)
            if g is not None:
                mode = "track"
            else:
                mode = "track" if rate >= a.min_hit else "blur"
                if mode == "track" and float(x.max() - x.min()) < 0.02 * W:
                    mode = "crop"  # subject never really moved: a still frame reads better than micro-pans
                    x = np.full(e - s, float(np.median(x)))
        xs[s:e] = x
        report.append(dict(shot=si, start=round(s / fps, 3), end=round(e / fps, 3), mode=mode,
                           detect_rate=round(rate, 2) if need_detect[si] else None, subjects=kind_counts,
                           crop_x=round(float(np.median(x)) / max_x, 3), pan_px=round(float(x.max() - x.min()))))

    plan = dict(input=a.input, fps=fps, frames=n, source=[W, H], crop=[cw, H], output=[a.width, a.height],
                shots=report)

    if a.plan_only:
        Path(a.output).write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(dict(shots=report), ensure_ascii=False, indent=1))
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="reframe_"))
    try:
        cmds = tmp / "crop.cmd"
        with cmds.open("w", encoding="utf-8") as f:
            last = None
            for k in range(n):
                v = int(round(xs[k]))
                if v != last:
                    f.write(f"{k / fps:.4f} crop x {v};\n")
                    last = v
        OW, OH = a.width, a.height
        # sendcmd reads a relative path from cwd, which sidesteps Windows drive-letter escaping in filtergraphs
        crop = f"sendcmd=f=crop.cmd,crop=w={cw}:h={H}:x={int(xs[0])}:y=0,scale={OW}:{OH}:flags=lanczos,setsar=1"
        blurs = [r for r in report if r["mode"] == "blur"]
        if blurs:
            # one pass for the whole file: blurred-background frames are laid over the crop only during blur shots,
            # so sound and picture never drift the way per-shot cut + join can
            enable = "+".join(f"between(t,{r['start']},{r['end'] - 0.5 / fps:.4f})" for r in blurs)
            fc = (f"[0:v]split=3[c][bg][fg];[c]{crop}[cv];"
                  f"[bg]scale={OW}:{OH}:force_original_aspect_ratio=increase,crop={OW}:{OH},boxblur=20:2,"
                  f"eq=brightness=-0.15[bgb];[fg]scale={OW}:-2:flags=lanczos[fgs];"
                  f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1[bl];"
                  f"[cv][bl]overlay=0:0:enable='{enable}'[v]")
        else:
            fc = f"[0:v]{crop}[v]"
        out = Path(a.output).resolve()
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(Path(a.input).resolve()),
               "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", str(a.crf),
               "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", str(out)]
        r = subprocess.run(cmd, cwd=tmp)
        if r.returncode:
            print("ffmpeg failed", file=sys.stderr)
            return r.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if a.debug:
        write_debug(a.input, a.debug, xs, cw, H, boxes, fps)

    print(json.dumps(dict(status="completed", output=str(out), shots=report), ensure_ascii=False, indent=1))
    return 0


def write_debug(src: str, dst: str, xs: np.ndarray, cw: int, H: int, boxes: dict, fps: float) -> None:
    cap = cv2.VideoCapture(src)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vw = cv2.VideoWriter(dst, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    last_box = None
    k = 0
    while True:
        ok, f = cap.read()
        if not ok or k >= len(xs):
            break
        last_box = boxes.get(k, last_box if k % 10 else None)
        x = int(xs[k])
        dim = f.copy()
        dim[:, :x] = dim[:, :x] // 3
        dim[:, x + cw:] = dim[:, x + cw:] // 3
        if last_box:  # what the detector found (amber), drawn over the dimming so it stays readable
            b = last_box
            cv2.rectangle(dim, (int(b["x"]), int(b["y"])), (int(b["x"] + b["w"]), int(b["y"] + b["h"])), (81, 196, 245), 3)
        cv2.rectangle(dim, (x, 0), (x + cw - 1, H - 1), (165, 237, 128), 5)  # crop window, brand mint
        vw.write(dim)
        k += 1
    vw.release()
    cap.release()


if __name__ == "__main__":
    sys.exit(main())
