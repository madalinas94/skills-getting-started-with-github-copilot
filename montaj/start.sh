#!/usr/bin/env sh
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "ffmpeg nu e instalat (macOS: brew install ffmpeg, Linux: sudo apt install ffmpeg)"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python server.py
