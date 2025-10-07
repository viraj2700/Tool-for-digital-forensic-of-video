# forensic/cli.py
import argparse
import os
from .forensic import build_report, ffprobe_metadata, file_hash

def main():
    parser = argparse.ArgumentParser(description="Simple Video Forensic Toolkit CLI")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--out", "-o", default="static/results", help="Output directory")
    parser.add_argument("--sample-every", type=int, default=30, help="Sample every N frames for thumbnails")
    parser.add_argument("--ela-scale", type=int, default=30, help="ELA amplification scale")
    args = parser.parse_args()

    video = args.video
    out = os.path.join(args.out, os.path.splitext(os.path.basename(video))[0])
    os.makedirs(out, exist_ok=True)
    print("Computing SHA256...")
    print(file_hash(video))
    print("Running report (this may take some minutes)...")
    report = build_report(video, out, every_n_frame=args.sample_every, ela_scale=args.ela_scale)
    print("Report saved to:", out)
    print("Top-level report keys:", list(report.keys()))

if __name__ == "__main__":
    main()
