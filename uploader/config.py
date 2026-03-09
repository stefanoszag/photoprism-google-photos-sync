"""Configuration settings for Google Photos uploader."""

from pathlib import Path

# Get the current directory (where config.py is)
CURRENT_DIR = Path(__file__).parent

# Google Photos API scopes required for uploading
SCOPES = [
    "https://www.googleapis.com/auth/photoslibrary",
    "https://www.googleapis.com/auth/photoslibrary.sharing",
    "https://www.googleapis.com/auth/photoslibrary.edit.appcreateddata",
    "https://www.googleapis.com/auth/photoslibrary.appendonly",
    "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata",
    "https://www.googleapis.com/auth/photoslibrary.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Path to store credentials
CREDENTIALS_FILE = str(CURRENT_DIR / "credentials.json")
TOKEN_FILE = str(CURRENT_DIR / "token.json")

# Path to the shared folder containing photos
SHARED_FOLDER = str(CURRENT_DIR.parent / "shared")
