# forensic/forensic.py
import os
import subprocess
import json
import hashlib
from PIL import Image, ImageChops, ImageStat
import cv2
import numpy as np
import math
from tqdm import tqdm
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# -------------------------
# Helpers: ffprobe metadata
# -------------------------
def ffprobe_metadata(path):
    """Return ffprobe JSON metadata dict for a video file."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe error: {p.stderr.decode(errors='ignore')}")
    return json.loads(p.stdout.decode())

# -------------------------
# Hashing
# -------------------------
def file_hash(path, algo="sha256", chunk_size=4*1024*1024):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

# -------------------------
# Extract audio (wav)
# -------------------------
def extract_audio(path, out_wav):
    cmd = ["ffmpeg", "-y", "-i", path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", out_wav]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction error: {p.stderr.decode(errors='ignore')}")
    return out_wav

# -------------------------
# Generate spectrogram image
# -------------------------
def audio_spectrogram(wav_path, out_png, dpi=150):
    import wave
    import numpy as np
    import matplotlib.pyplot as plt

    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        nframes = wf.getnframes()
        data = wf.readframes(nframes)
        channels = wf.getnchannels()
        arr = np.frombuffer(data, dtype=np.int16)
        if channels == 2:
            arr = arr.reshape(-1, 2).mean(axis=1)  # mono

    plt.figure(figsize=(8, 3), dpi=dpi)
    plt.specgram(arr, Fs=sr, cmap="inferno")
    plt.xlabel("Time (s)")
    plt.ylabel("Frequency (Hz)")
    plt.colorbar(label="Intensity dB")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()
    return out_png

# -------------------------
# Extract frames (every Nth frame or interval seconds)
# -------------------------
def extract_frames(video_path, out_dir, every_n_frame=30, max_frames=None, start_time=None, duration=None):
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Cannot open video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_idx = 0
    saved = 0
    pbar = tqdm(total=total if total>0 else None, desc="Extract frames", unit="f")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % every_n_frame == 0:
            fname = os.path.join(out_dir, f"frame_{frame_idx:08d}.jpg")
            cv2.imwrite(fname, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            saved += 1
            if max_frames and saved >= max_frames:
                break
        frame_idx += 1
        pbar.update(1)
    pbar.close()
    cap.release()
    return saved

# -------------------------
# Scene change / splice detection (simple histogram-diff)
# -------------------------
def scene_changes(video_path, threshold=0.5, min_distance_frames=5):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Cannot open video")
    prev_hist = None
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    changes = []
    idx = 0
    distances = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0,1], None, [50,60], [0,180,0,256])
        cv2.normalize(hist, hist)
        if prev_hist is not None:
            d = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
            distances.append((idx, d))
            if d > threshold:
                # ensure minimum separation
                if not changes or idx - changes[-1] >= min_distance_frames:
                    changes.append(idx)
        prev_hist = hist
        idx += 1
    cap.release()
    return changes, distances, fps

# -------------------------
# ELA on a single frame (image)
# -------------------------
def ela_image_analysis(img_path, out_path, scale=30):
    """Perform Error Level Analysis on a saved JPEG image.
    Save ELA image to out_path and return max difference statistic."""
    orig = Image.open(img_path).convert("RGB")
    # re-save at 95 quality to temporary in-memory
    tmp_path = out_path + ".tmp.jpg"
    orig.save(tmp_path, "JPEG", quality=95)
    comp = Image.open(tmp_path).convert("RGB")
    diff = ImageChops.difference(orig, comp)
    # amplify
    extrema = diff.getextrema()
    # scale differences
    def scale_img(img, factor):
        arr = np.array(img).astype(np.float32)
        arr *= factor
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)
    scaled = scale_img(diff, scale)
    scaled.save(out_path)
    stat = ImageStat.Stat(diff)
    max_diff = max(stat.extrema[i][1] for i in range(3)) if stat.extrema else 0
    try:
        os.remove(tmp_path)
    except Exception:
        pass
    return max_diff

# -------------------------
# Duplicate-frame / copy detection (simple hashing)
# -------------------------
def frame_hashes(video_path, sample_every_n=10, hash_size=(16,16)):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Cannot open video")
    idx = 0
    hashes = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % sample_every_n == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, hash_size, interpolation=cv2.INTER_AREA)
            # simple perceptual hash (mean)
            mean = small.mean()
            bits = (small > mean).flatten()
            h = ''.join(['1' if b else '0' for b in bits])
            hashes.append((idx, h))
        idx += 1
    cap.release()
    return hashes

def find_duplicate_hashes(hashes):
    index = {}
    duplicates = []
    for idx, h in hashes:
        index.setdefault(h, []).append(idx)
    for h, lst in index.items():
        if len(lst) > 1:
            duplicates.append((h, lst))
    return duplicates

# -------------------------
# GOP analysis / bitrate by segment (uses ffprobe packet info)
# -------------------------
def stream_bitrate_stats(path):
    """Get basic bitrate and duration info from ffprobe JSON"""
    md = ffprobe_metadata(path)
    fmt = md.get("format", {})
    bit_rate = fmt.get("bit_rate")
    duration = float(fmt.get("duration", 0))
    size = int(fmt.get("size", 0)) if fmt.get("size") else None
    return {"bit_rate": bit_rate, "duration": duration, "size": size, "format_name": fmt.get("format_name")}

# -------------------------
# Quick report builder
# -------------------------
def build_report(video_path, work_dir, every_n_frame=30, ela_scale=30):
    os.makedirs(work_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(video_path))[0]
    # metadata
    meta = ffprobe_metadata(video_path)
    # hash
    sha256 = file_hash(video_path, "sha256")
    # basic stats
    stats = stream_bitrate_stats(video_path)
    # extract frames (sampled)
    frame_dir = os.path.join(work_dir, "frames")
    os.makedirs(frame_dir, exist_ok=True)
    saved = extract_frames(video_path, frame_dir, every_n_frame=every_n_frame, max_frames=200)
    # run ELA on first few frames
    ela_dir = os.path.join(work_dir, "ela")
    os.makedirs(ela_dir, exist_ok=True)
    ela_results = {}
    for i, fname in enumerate(sorted(os.listdir(frame_dir))[:min(20, len(os.listdir(frame_dir)))]):
        fpath = os.path.join(frame_dir, fname)
        out_ela = os.path.join(ela_dir, f"ela_{fname}")
        maxdiff = ela_image_analysis(fpath, out_ela, scale=ela_scale)
        ela_results[fname] = {"ela_image": out_ela, "max_diff": maxdiff}
    # scene changes
    sc_changes, sc_distances, fps = scene_changes(video_path, threshold=0.5, min_distance_frames=5)
    # frame hashes & duplicates
    hashes = frame_hashes(video_path, sample_every_n=10)
    duplicates = find_duplicate_hashes(hashes)
    # audio spectrogram
    wav_out = os.path.join(work_dir, f"{base}_audio.wav")
    spec_out = os.path.join(work_dir, f"{base}_spectrogram.png")
    try:
        extract_audio(video_path, wav_out)
        audio_spectrogram(wav_out, spec_out)
    except Exception as e:
        spec_out = None

    report = {
        "file": video_path,
        "sha256": sha256,
        "metadata": meta,
        "stats": stats,
        "frames_saved": saved,
        "ela": ela_results,
        "scene_changes": {"frames": sc_changes, "fps": fps},
        "hash_duplicates": duplicates,
        "audio_spectrogram": spec_out
    }
    # save report JSON
    import json
    with open(os.path.join(work_dir, f"{base}_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    return report
