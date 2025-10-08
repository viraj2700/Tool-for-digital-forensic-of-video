# CSDF — Digital Video Forensics Toolkit

## Overview
CSDF is a lightweight, modular toolkit for basic video forensic analysis:
- metadata extraction (ffprobe)
- SHA256 hashing
- frame extraction
- Error Level Analysis (ELA) on extracted frames
- a modern Flask web UI to upload and inspect results

## Install
1. Create venv and install:
   ```bash
   python -m venv venv
   source venv/bin/activate   # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
