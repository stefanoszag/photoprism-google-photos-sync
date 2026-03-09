import os

USERNAME = os.environ.get("PHOTOPRISM_USERNAME")
PASSWORD = os.environ.get("PHOTOPRISM_PASSWORD")
PHOTOPRISM_URL = os.environ.get("PHOTOPRISM_SERVER_URL") or os.environ.get(
    "PHOTOPRISM_URL", "http://192.168.1.119:2342"
)
NUM_RANDOM_ALBUMS = int(os.environ.get("NUM_RANDOM_ALBUMS", 5))
NUM_RANDOM_PHOTOS = int(os.environ.get("NUM_RANDOM_PHOTOS", 5))
