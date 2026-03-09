import logging
import random
from pathlib import Path

import pandas as pd
import requests

from . import auth, config

# Configure logging
logger = logging.getLogger(__name__)


class PhotoPrismAPI:
    def __init__(self):
        self.token = auth.get_token(config.PHOTOPRISM_URL)
        self.headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        self.headers_download = {"Authorization": f"Bearer {self.token}", "Accept": "application/octet-stream"}
        # Create shared directory if it doesn't exist
        self.photos_dir = Path("shared")
        self.photos_dir.mkdir(exist_ok=True)

    def clean_photos_directory(self):
        """Delete all files in the photos directory"""
        if self.photos_dir.exists():
            for file in self.photos_dir.iterdir():
                if file.is_file():
                    file.unlink()
            logger.info("Cleaned photos directory")

    def get_albums(self):
        try:
            url = f"{config.PHOTOPRISM_URL}/api/v1/albums?count=1000&offset=0&type=album"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            albums = response.json()
            return albums

        except requests.exceptions.RequestException as e:
            logger.error(f"Error during request: {e}")
            if hasattr(e.response, "text"):
                logger.error(f"Response content: {e.response.text}")
            return None

    def process_whitelist(self):
        # Read the whitelist CSV
        current_dir = Path(__file__).parent
        whitelist_df = pd.read_csv(current_dir / "data/album_whitelist.csv")

        # Get all albums
        all_albums = self.get_albums()
        if not all_albums:
            return None

        # Create a dictionary of album titles to UIDs
        album_uid_map = {album["Title"]: album["UID"] for album in all_albums}

        # Add UID column to whitelist dataframe
        whitelist_df["uid"] = whitelist_df["album_title"].map(album_uid_map)

        # Log albums that weren't found
        missing_albums = whitelist_df[whitelist_df["uid"].isna()]
        if not missing_albums.empty:
            logger.warning("Albums not found in PhotoPrism:")
            for album in missing_albums["album_title"]:
                logger.warning(f"- {album}")

        return whitelist_df

    def get_random_albums(self):
        # Get the whitelist with UIDs
        whitelist_df = self.process_whitelist()
        if whitelist_df is None:
            return None

        # Filter out any albums that weren't found (UID is NA)
        valid_albums = whitelist_df.dropna(subset=["uid"])

        if len(valid_albums) < config.NUM_RANDOM_ALBUMS:
            logger.warning(f"Only {len(valid_albums)} valid albums found, returning all of them")
            n = len(valid_albums)
        else:
            n = config.NUM_RANDOM_ALBUMS

        # Randomly select n albums
        selected = valid_albums.sample(n=n)

        logger.info("Selected Albums:")
        for _, row in selected.iterrows():
            logger.debug(f"Title: {row['album_title']}, UID: {row['uid']}")

        return selected[["album_title", "uid"]]

    def get_album_photos(self, album_uids):
        all_photo_uids = []

        for uid in album_uids:
            try:
                # Using the correct endpoint to get photos from an album
                url = f"{config.PHOTOPRISM_URL}/api/v1/photos/?count=1000&s={uid}"
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                photos = response.json()

                # Extract only the UIDs from the photos
                photo_uids = [photo["UID"] for photo in photos]
                logger.debug(f"Found {len(photo_uids)} photos in album {uid}")
                all_photo_uids.extend(photo_uids)

            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching photos for album {uid}: {e}")
                if hasattr(e.response, "text"):
                    logger.error(f"Response content: {e.response.text}")

        logger.info(f"Total photo UIDs found across all albums: {len(all_photo_uids)}")

        # Randomly select the specified number of photos
        if len(all_photo_uids) < config.NUM_RANDOM_PHOTOS:
            logger.warning(f"Only {len(all_photo_uids)} photos found, returning all of them")
            selected_photos = all_photo_uids
        else:
            selected_photos = random.sample(all_photo_uids, config.NUM_RANDOM_PHOTOS)

        logger.info(f"Randomly selected {len(selected_photos)} photos")
        return selected_photos

    def download_photos(self, photo_uids):
        # Clean the photos directory before downloading new photos
        self.clean_photos_directory()

        downloaded_files = []

        for uid in photo_uids:
            try:
                # Get the download URL for the photo
                url = f"{config.PHOTOPRISM_URL}/api/v1/photos/{uid}/dl"
                response = requests.get(url, headers=self.headers_download, stream=True)
                response.raise_for_status()

                # Get the filename from the Content-Disposition header or use UID
                filename = response.headers.get("Content-Disposition", "").split("filename=")[-1].strip('"')
                if not filename:
                    filename = f"{uid}.jpg"

                # Save the photo
                filepath = self.photos_dir / filename
                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                logger.debug(f"Downloaded: {filename}")
                downloaded_files.append(filepath)

            except requests.exceptions.RequestException as e:
                logger.error(f"Error downloading photo {uid}: {e}")
                if hasattr(e.response, "text"):
                    logger.error(f"Response content: {e.response.text}")

        logger.info(f"Successfully downloaded {len(downloaded_files)} photos to {self.photos_dir}")
        return downloaded_files


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    api = PhotoPrismAPI()
    selected_albums = api.get_random_albums()
    if selected_albums is not None:
        album_uids = selected_albums["uid"].tolist()
        photo_uids = api.get_album_photos(album_uids)
        logger.debug("Selected Photo UIDs:")
        logger.debug(photo_uids)

        # Download the selected photos
        downloaded_files = api.download_photos(photo_uids)
