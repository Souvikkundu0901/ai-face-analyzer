"""
Vercel serverless entrypoint for FastAPI application.
Configures headless environment flags and exposes top-level 'app' callable.
"""
import sys
import os
from pathlib import Path

# Force headless environment flags for OpenCV and MediaPipe on Linux serverless
os.environ["OPENCV_HEADLESS"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Add project root directory to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.main import app

handler = app
application = app
