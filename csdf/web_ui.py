# web_ui.py
import os
from flask import Flask, request, render_template, redirect, url_for, send_from_directory
from forensic.forensic import build_report
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "static/results"
THUMBS_FOLDER = "static/thumbs"
ALLOWED_EXT = {"mp4","mov","avi","mkv","webm"}

app = Flask(__name__, template_folder="templates")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)
os.makedirs(THUMBS_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        f = request.files.get("file")
        if not f:
            return "No file", 400
        if not allowed_file(f.filename):
            return "Unsupported extension", 400
        filename = secure_filename(f.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(path)
        outdir = os.path.join(RESULTS_FOLDER, os.path.splitext(filename)[0])
        os.makedirs(outdir, exist_ok=True)
        # run report synchronously
        report = build_report(path, outdir)
        return redirect(url_for("result", name=os.path.splitext(filename)[0]))
    return render_template("index.html")

@app.route("/result/<name>")
def result(name):
    folder = os.path.join(RESULTS_FOLDER, name)
    report_file = os.path.join(folder, f"{name}_report.json")
    if not os.path.exists(report_file):
        return "Report not found", 404
    import json
    with open(report_file, "r") as f:
        report = json.load(f)
    # build lists of thumbnails and ela images
    frames_dir = os.path.join(folder, "frames")
    ela_dir = os.path.join(folder, "ela")
    frame_list = sorted(os.listdir(frames_dir)) if os.path.exists(frames_dir) else []
    ela_list = sorted(os.listdir(ela_dir)) if os.path.exists(ela_dir) else []
    return render_template("result.html", name=name, report=report, frames=frame_list, ela=ela_list, folder=folder)

@app.route("/static/results/<name>/<path:filename>")
def result_file(name, filename):
    folder = os.path.join(RESULTS_FOLDER, name)
    return send_from_directory(folder, filename)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
