# web_ui.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from forensic.forensic import analyze_video
import json

UPLOAD_FOLDER = "uploads"
ALLOWED = {"mp4", "mov", "avi", "mkv", "webm"}

app = Flask(__name__)
app.secret_key = "replace-with-secure-key"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("static/results", exist_ok=True)
os.makedirs("static/thumbs", exist_ok=True)

def allowed_file(name):
    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        f = request.files.get("file")
        if not f or f.filename == "":
            flash("No file selected")
            return redirect(request.url)
        if not allowed_file(f.filename):
            flash("File type not allowed")
            return redirect(request.url)
        filename = secure_filename(f.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(path)

        # Run analysis (blocking). For long files use background queue.
        summary = analyze_video(path, output_dir="static/results", max_frames=20, every_nth=30)
        return redirect(url_for("result", base=summary["base"]))
    return render_template("index.html")

@app.route("/result/<base>")
def result(base):
    report_path = os.path.join("static", "results", f"{base}.json")
    if not os.path.exists(report_path):
        # Try nested folder name
        report_path = os.path.join("static", "results", base, f"{base}_report.json")
        if not os.path.exists(report_path):
            flash("Report not ready or missing.")
            return redirect(url_for('index'))
    with open(report_path, "r", encoding="utf-8") as fh:
        report = json.load(fh)

    # Generate gallery list (frames + ela)
    thumbs_dir = os.path.join("static", "thumbs", base)
    frames = []
    if os.path.isdir(thumbs_dir):
        for fname in sorted(os.listdir(thumbs_dir)):
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                frames.append(url_for('static', filename=f"thumbs/{base}/{fname}"))

    # Prepare a clean metadata dict for display (only non-empty)
    meta_display = {
        "File Name": report.get("filename"),
        "Duration (s)": report.get("duration_s"),
        "Resolution": report.get("resolution"),
        "Frame Rate (fps)": report.get("fps"),
        "Codec": report.get("codec"),
        "Container": report.get("format"),
        "Created": report.get("creation_time"),
        "Device": " ".join(filter(None, [report.get("device_make"), report.get("device_model")])),
        "GPS (raw)": report.get("gps"),
        "Orientation": report.get("orientation"),
        "File SHA256": report.get("sha256")
    }
    # remove None/empty
    meta_display = {k: v for k, v in meta_display.items() if v not in (None, "", [], {})}

    return render_template("result_pretty.html", meta=meta_display, frames=frames, base=base, report_path=report_path)

@app.route("/download/report/<base>")
def download_report(base):
    path = os.path.join("static", "results", f"{base}.json")
    if not os.path.exists(path):
        path = os.path.join("static", "results", base, f"{base}_report.json")
        if not os.path.exists(path):
            flash("Report not found")
            return redirect(url_for('index'))
    return send_from_directory("static/results", os.path.basename(path), as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
