# forensic/forensic.py
import os, json, shutil
from .metadata_extractor import pick_relevant_metadata
from .hash_checker import compute_sha256
from .frame_extractor import extract_frames
from .ela import ela_from_image
from .orientation_detector import detect_rotation_from_metadata
from .metadata_extractor import ffprobe_json
from datetime import datetime

def analyze_video(video_path, output_dir="static/results", max_frames=20, every_nth=30):
    """
    Friendly pipeline: metadata (reduced) -> hash -> extract frames -> ELA -> compact JSON
    Returns a summary dict for UI usage.
    """
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(video_path))[0]

    # Full ffprobe meta (used by orientation detector)
    full_meta = ffprobe_json(video_path)
    orientation = detect_rotation_from_metadata(full_meta)

    # Pick reduced metadata
    meta = pick_relevant_metadata(video_path)

    # Hash
    sha256 = compute_sha256(video_path)

    # Prepare result directories
    result_dir = os.path.join(output_dir, base)
    thumbs_dir = os.path.join("static", "thumbs", base)
    os.makedirs(result_dir, exist_ok=True)
    os.makedirs(thumbs_dir, exist_ok=True)

    # Extract frames (sampled)
    frames = extract_frames(video_path, thumbs_dir, max_frames=max_frames, every_nth=every_nth)

    frames_info = []
    for f in frames:
        ela_path = os.path.join(thumbs_dir, "ela_" + os.path.basename(f))
        ela_from_image(f, ela_path)
        frames_info.append({
            "frame_file": f.replace("\\", "/"),
            "ela_file": ela_path.replace("\\", "/"),
            "frame_hash": compute_sha256(f)
        })

    # Build compact report (only essential fields)
    report = {
        "filename": meta.get("filename"),
        "sha256": sha256,
        "filesize_bytes": meta.get("size_bytes"),
        "duration_s": meta.get("duration_s"),
        "resolution": meta.get("resolution"),
        "fps": meta.get("fps"),
        "codec": meta.get("codec"),
        "format": meta.get("format_name"),
        "creation_time": meta.get("creation_time"),
        "device_make": meta.get("device_make"),
        "device_model": meta.get("device_model"),
        "gps": meta.get("gps_raw"),
        "orientation": orientation,
        "frames": frames_info,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }

    # Save JSON in two places: folder and top-level results
    report_path = os.path.join(result_dir, f"{base}_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    top_report = os.path.join(output_dir, f"{base}.json")
    shutil.copyfile(report_path, top_report)

    return {
        "base": base,
        "report_path": top_report.replace("\\", "/"),
        "thumbs_dir": thumbs_dir.replace("\\", "/"),
        "frames_count": len(frames),
        "report": report
    }
