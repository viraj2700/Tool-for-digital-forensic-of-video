# forensic/metadata_extractor.py
import subprocess, json
from datetime import datetime

def ffprobe_json(path):
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {}

def pick_relevant_metadata(path):
    """
    Return a simplified metadata dict with only relevant video fields.
    """
    meta = ffprobe_json(path)
    out = {}
    fmt = meta.get("format", {})
    streams = meta.get("streams", [])

    # Basic format-level info
    out["filename"] = fmt.get("filename") or path.split("/")[-1]
    if fmt.get("duration"):
        try:
            out["duration_s"] = round(float(fmt.get("duration")), 2)
        except Exception:
            out["duration_s"] = fmt.get("duration")
    out["size_bytes"] = int(fmt.get("size")) if fmt.get("size") else None

    # Try creation time from format tags
    tags = fmt.get("tags", {}) or {}
    creation = tags.get("creation_time") or tags.get("com.apple.quicktime.creationdate")
    if creation:
        # normalize
        try:
            out["creation_time"] = datetime.fromisoformat(creation.replace("Z", "+00:00")).isoformat()
        except Exception:
            out["creation_time"] = creation

    # find the first video stream
    video_stream = None
    for s in streams:
        if s.get("codec_type") == "video":
            video_stream = s
            break

    if video_stream:
        out["codec"] = video_stream.get("codec_long_name") or video_stream.get("codec_name")
        out["width"] = video_stream.get("width")
        out["height"] = video_stream.get("height")
        # resolution string
        if out["width"] and out["height"]:
            out["resolution"] = f"{out['width']}x{out['height']}"
        # frame rate
        fr = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
        # avg_frame_rate can be "30/1"
        try:
            if fr and "/" in fr:
                num, den = fr.split("/")
                out["fps"] = round(float(num) / float(den), 2) if float(den) != 0 else fr
            else:
                out["fps"] = float(fr) if fr else None
        except Exception:
            out["fps"] = fr

        # device (if present in tags)
        vtags = video_stream.get("tags", {}) or {}
        out["device_make"] = vtags.get("com.apple.quicktime.make") or vtags.get("make")
        out["device_model"] = vtags.get("com.apple.quicktime.model") or vtags.get("model")
        # GPS (Apple QuickTime location tag appears like "+18.4437+073.8858+671.001/")
        loc = vtags.get("com.apple.quicktime.location.ISO6709") or vtags.get("location")
        if loc:
            out["gps_raw"] = loc

    # friendly format name (container)
    out["format_name"] = fmt.get("format_long_name") or fmt.get("format_name")
    return out
