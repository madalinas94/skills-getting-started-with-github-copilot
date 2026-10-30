"""Montaj.exe: starts the bundled Python with the app and opens the browser.

Folder layout (built by .github/workflows/montaj-windows.yml):
    Montaj.exe  python/  ffmpeg/  app/
"""

import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
env = dict(os.environ, MONTAJ_FFMPEG_DIR=str(root / "ffmpeg"), PYTHONUTF8="1",
           MONTAJ_WORKSPACE=str(Path(os.environ.get("USERPROFILE", root)) / "Montaj"))
print("Montaj pornește… se deschide în browser la http://127.0.0.1:8765")
print("Lasă fereastra asta deschisă cât lucrezi. Închide-o ca să oprești Montaj.\n")
try:
    sys.exit(subprocess.call([str(root / "python" / "python.exe"), "server.py"], cwd=root / "app", env=env))
except KeyboardInterrupt:
    pass
