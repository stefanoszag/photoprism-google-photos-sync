"""Configuration settings for the image resizer."""

import os
from pathlib import Path

# Get the current directory (where config.py is)
CURRENT_DIR = Path(__file__).parent

# Path to the shared folder containing photos (same as downloader/uploader)
SHARED_FOLDER = str(CURRENT_DIR.parent / "shared")

# Resize behaviour
RESIZE_ENABLED = os.getenv("RESIZE_ENABLED", "false").lower() == "true"
RESIZE_PERCENTAGE = int(os.getenv("RESIZE_PERCENTAGE", "100"))
