"""Main module for uploading photos to Google Photos."""

import logging
import mimetypes
import os
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from utils.alerts import AlertManager

from .auth import get_credentials
from .config import SHARED_FOLDER

# Configure logging
logger = logging.getLogger(__name__)

# Initialize alert manager
alert_manager = AlertManager()


def get_media_type(file_path: str) -> str:
    """Determine the media type of a file."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and mime_type.startswith("image/"):
        return mime_type
    return None


def list_photos(folder_path: str) -> list:
    """List all photos in the specified folder."""
    photos = []
    folder = Path(folder_path)

    for file_path in folder.glob("*"):
        if get_media_type(str(file_path)):
            photos.append(str(file_path))

    return photos


def get_or_create_album(service, album_title: str) -> str:
    """Get or create an album with the specified title.

    Args:
        service: Google Photos API service instance
        album_title: Title of the album

    Returns:
        str: Album ID
    """
    # First, try to find existing album
    response = service.albums().list().execute()

    if "albums" in response:
        for album in response["albums"]:
            if album["title"] == album_title:
                logger.info(f"Found existing album: {album_title}")
                return album["id"]

    # If not found, create new album
    logger.info(f"Creating new album: {album_title}")
    response = service.albums().create(body={"album": {"title": album_title}}).execute()
    return response["id"]


def upload_photo(service, credentials: Credentials, photo_path: str, album_id: str = None) -> bool:
    """Upload a single photo to Google Photos.

    Args:
        service: Google Photos API service instance
        credentials: Google OAuth2 credentials
        photo_path: Path to the photo file
        album_id: Optional album ID to add the photo to

    Returns:
        bool: True if upload was successful, False otherwise
    """
    try:
        # First, upload the media
        file_path = Path(photo_path)
        mime_type = get_media_type(str(file_path))

        if not mime_type:
            logger.warning(f"Skipping {file_path.name} - not a supported image type")
            return False

        # First step: Upload the bytes
        logger.debug(f"Uploading bytes for {file_path.name}...")
        upload_url = "https://photoslibrary.googleapis.com/v1/uploads"
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": mime_type,
            "X-Goog-Upload-Protocol": "raw",
        }

        import requests

        with open(photo_path, "rb") as image_file:
            response = requests.post(upload_url, headers=headers, data=image_file)

        if response.status_code != 200:
            logger.error(f"Failed to upload bytes for {file_path.name} - Status code: {response.status_code}")
            logger.error(f"Response content: {response.content}")
            return False

        upload_token = response.content.decode("utf-8")

        # Second step: Create the media item
        new_media_item = {"description": "", "simpleMediaItem": {"uploadToken": upload_token}}

        request_body = {"newMediaItems": [new_media_item]}

        # If album_id is provided, add it to the request
        if album_id:
            request_body["albumId"] = album_id

        response = service.mediaItems().batchCreate(body=request_body).execute()

        if response.get("newMediaItemResults"):
            result = response["newMediaItemResults"][0]
            if result.get("status", {}).get("message") == "Success":
                logger.debug(f"Successfully uploaded {file_path.name}")

                # If we have an album_id but it wasn't included in the initial upload,
                # add the photo to the album separately
                if album_id and "albumId" not in request_body:
                    media_item_id = result["mediaItem"]["id"]
                    add_to_album_request = {"mediaItemIds": [media_item_id]}
                    service.albums().batchAddMediaItems(albumId=album_id, body=add_to_album_request).execute()
                    logger.debug(f"Added {file_path.name} to album")

                return True
            else:
                logger.error(
                    f"Failed to create media item for {file_path.name} - {result.get('status', {}).get('message')}"
                )
                return False

        return False

    except Exception as e:
        logger.error(f"Error uploading {photo_path}: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return False


def cleanup_album(service, credentials: Credentials, album_id: str) -> bool:
    """Remove all photos from the album.
    Note: Due to Google Photos API limitations, photos can only be removed from the album,
    not permanently deleted from Google Photos.

    Args:
        service: Google Photos API service instance
        credentials: Google OAuth2 credentials
        album_id: ID of the album to clean

    Returns:
        bool: True if cleanup was successful
    """
    try:
        # Get all media items in the album
        logger.info("Fetching existing photos in the album...")
        response = service.mediaItems().search(body={"albumId": album_id}).execute()

        if not response.get("mediaItems"):
            logger.info("No existing photos found in the album.")
            return True

        media_items = response.get("mediaItems", [])
        logger.info(f"Found {len(media_items)} existing photos in the album.")

        # Remove items from the album
        logger.info("Removing photos from album...")
        media_item_ids = [item["id"] for item in media_items]

        # Remove items from album in batches of 50 (API limit)
        batch_size = 50
        for i in range(0, len(media_item_ids), batch_size):
            batch = media_item_ids[i : i + batch_size]
            request_body = {"mediaItemIds": batch}
            service.albums().batchRemoveMediaItems(albumId=album_id, body=request_body).execute()
            logger.debug(f"Removed batch of {len(batch)} photos from album")

        return True

    except Exception as e:
        logger.error(f"Error cleaning up album: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return False


def cleanup_shared_folder(photos: list) -> bool:
    """Delete all successfully uploaded photos from the shared folder.

    Args:
        photos: List of photo paths that were uploaded

    Returns:
        bool: True if cleanup was successful
    """
    try:
        logger.info("Cleaning up shared folder...")
        for photo in photos:
            try:
                os.remove(photo)
                logger.debug(f"Deleted {Path(photo).name}")
            except Exception as e:
                logger.error(f"Failed to delete {Path(photo).name}: {str(e)}")
                return False

        logger.info("Successfully cleaned up shared folder.")
        return True

    except Exception as e:
        logger.error(f"Error cleaning up shared folder: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return False


def get_storage_quota(credentials: Credentials) -> dict:
    """Get Google Drive storage quota information.

    Args:
        credentials: Google OAuth2 credentials

    Returns:
        dict: Storage quota information including usage and limit
    """
    try:
        # Build the Drive API service
        drive_service = build("drive", "v3", credentials=credentials)

        # Get the storage quota
        about = drive_service.about().get(fields="storageQuota").execute()
        quota = about.get("storageQuota", {})

        # Convert bytes to GB for better readability
        usage_gb = int(quota.get("usage", 0)) / (1024 * 1024 * 1024)
        limit_gb = int(quota.get("limit", 0)) / (1024 * 1024 * 1024)

        return {
            "usage_gb": round(usage_gb, 2),
            "limit_gb": round(limit_gb, 2),
            "usage_bytes": int(quota.get("usage", 0)),
            "limit_bytes": int(quota.get("limit", 0)),
        }
    except Exception as e:
        logger.error(f"Error getting storage quota: {str(e)}")
        return None


def upload_to_album():
    """Upload all photos from shared folder to the Photoprism album."""
    start_time = datetime.now()
    summary = {
        "start_time": start_time,
        "end_time": None,
        "initial_storage": None,
        "final_storage": None,
        "total_photos": 0,
        "successful_uploads": 0,
        "failed_uploads": 0,
        "errors": [],
        "warnings": [],
    }

    try:
        # Get credentials and build service
        logger.info("Getting credentials...")
        creds = get_credentials()

        # Check storage quota before uploading
        quota = get_storage_quota(creds)
        if quota:
            usage_percent = quota["usage_bytes"] / quota["limit_bytes"] * 100
            logger.info(
                f"Current storage usage: {quota['usage_gb']}GB out of {quota['limit_gb']}GB "
                f"({usage_percent:.1f}% used)"
            )

            summary["initial_storage"] = {
                "usage_gb": quota["usage_gb"],
                "limit_gb": quota["limit_gb"],
                "usage_percent": usage_percent,
            }

            # Alert if storage usage is over 95%
            if usage_percent > 95:
                warning_msg = f"High storage usage: {usage_percent:.1f}%"
                summary["warnings"].append(warning_msg)
                alert_manager.send_alert(
                    subject="High Storage Usage",
                    message=f"⚠️ Google Drive storage usage is at {usage_percent:.1f}%\n"
                    f"Used: {quota['usage_gb']}GB\n"
                    f"Limit: {quota['limit_gb']}GB",
                    methods=["telegram"],
                )

        service = build(
            "photoslibrary",
            "v1",
            credentials=creds,
            discoveryServiceUrl="https://photoslibrary.googleapis.com/$discovery/rest?version=v1",
        )
        logger.info("Successfully authenticated with Google Photos API")

        # Get or create the Photoprism album
        album_id = get_or_create_album(service, "Photoprism")

        # Clean up existing photos in the album
        if not cleanup_album(service, creds, album_id):
            error_msg = "Failed to clean up album. Aborting upload."
            summary["errors"].append(error_msg)
            logger.error(error_msg)
            alert_manager.send_alert(subject="Album Cleanup Failed", message=f"❌ {error_msg}", methods=["telegram"])
            return

        # List all photos in the shared folder
        photos = list_photos(SHARED_FOLDER)

        if not photos:
            warning_msg = "No photos found in the shared folder."
            summary["warnings"].append(warning_msg)
            logger.warning(warning_msg)
            return

        logger.info(f"Found {len(photos)} photos to upload to Photoprism album.")
        summary["total_photos"] = len(photos)

        # Upload each photo
        successful_uploads = []
        failed_uploads = []
        for photo in photos:
            if upload_photo(service, creds, photo, album_id):
                successful_uploads.append(photo)
            else:
                failed_uploads.append(photo)

        # Log upload results
        summary["successful_uploads"] = len(successful_uploads)
        summary["failed_uploads"] = len(failed_uploads)

        logger.info(
            f"Upload complete. Successfully uploaded {summary['successful_uploads']} out of {summary['total_photos']} photos."
        )

        # Alert if any uploads failed
        if failed_uploads:
            failed_files = "\n".join([f"- {Path(p).name}" for p in failed_uploads])
            error_msg = f"{len(failed_uploads)} uploads failed: {failed_files}"
            summary["errors"].append(error_msg)
            alert_manager.send_alert(
                subject="Upload Failures",
                message=f"⚠️ {len(failed_uploads)} out of {summary['total_photos']} uploads failed\n\n"
                f"Failed files:\n{failed_files}",
                methods=["telegram"],
            )

        # Check storage quota after uploading
        quota = get_storage_quota(creds)
        if quota:
            usage_percent = quota["usage_bytes"] / quota["limit_bytes"] * 100
            logger.info(
                f"Updated storage usage: {quota['usage_gb']}GB out of {quota['limit_gb']}GB "
                f"({usage_percent:.1f}% used)"
            )

            summary["final_storage"] = {
                "usage_gb": quota["usage_gb"],
                "limit_gb": quota["limit_gb"],
                "usage_percent": usage_percent,
            }

            # Alert if storage usage is over 95%
            if usage_percent > 95:
                warning_msg = f"High storage usage after upload: {usage_percent:.1f}%"
                summary["warnings"].append(warning_msg)
                alert_manager.send_alert(
                    subject="High Storage Usage After Upload",
                    message=f"⚠️ Google Drive storage usage is at {usage_percent:.1f}%\n"
                    f"Used: {quota['usage_gb']}GB\n"
                    f"Limit: {quota['limit_gb']}GB",
                    methods=["telegram"],
                )

        # Clean up the shared folder if all uploads were successful
        if summary["successful_uploads"] == summary["total_photos"]:
            if cleanup_shared_folder(photos):
                logger.info("All operations completed successfully.")
            else:
                error_msg = "Uploads successful but failed to clean up shared folder."
                summary["errors"].append(error_msg)
                logger.error(error_msg)
                alert_manager.send_alert(subject="Cleanup Failed", message=f"⚠️ {error_msg}", methods=["telegram"])
        else:
            warning_msg = "Some uploads failed. Skipping shared folder cleanup to preserve files."
            summary["warnings"].append(warning_msg)
            logger.warning(warning_msg)
            alert_manager.send_alert(
                subject="Incomplete Upload",
                message=f"⚠️ {warning_msg}\n"
                f"Successful: {summary['successful_uploads']}\n"
                f"Failed: {summary['failed_uploads']}\n"
                f"Total: {summary['total_photos']}",
                methods=["telegram"],
            )

    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        summary["errors"].append(error_msg)
        logger.error(error_msg)
        import traceback

        stack_trace = traceback.format_exc()
        logger.error(stack_trace)
        alert_manager.send_alert(
            subject="Critical Error", message=f"❌ {error_msg}\n\nStack trace:\n{stack_trace}", methods=["telegram"]
        )

    finally:
        # Send execution summary
        summary["end_time"] = datetime.now()
        duration = summary["end_time"] - summary["start_time"]

        summary_msg = [
            "📊 *Execution Summary*",
            f"Start Time: {summary['start_time'].strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {duration.total_seconds():.1f} seconds",
            "",
            "*Upload Statistics*",
            f"Total Photos: {summary['total_photos']}",
            f"Successful: {summary['successful_uploads']}",
            f"Failed: {summary['failed_uploads']}",
            "",
        ]

        if summary["initial_storage"]:
            summary_msg.extend(
                [
                    "*Storage Usage*",
                    f"Initial: {summary['initial_storage']['usage_gb']}GB ({summary['initial_storage']['usage_percent']:.1f}%)",
                    f"Final: {summary['final_storage']['usage_gb']}GB ({summary['final_storage']['usage_percent']:.1f}%)"
                    if summary["final_storage"]
                    else "Final: Not available",
                    "",
                ]
            )

        if summary["warnings"]:
            summary_msg.extend(["*Warnings*", *[f"⚠️ {w}" for w in summary["warnings"]], ""])

        if summary["errors"]:
            summary_msg.extend(["*Errors*", *[f"❌ {e}" for e in summary["errors"]], ""])

        alert_manager.send_alert(subject="Execution Summary", message="\n".join(summary_msg), methods=["telegram"])


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Upload all photos to the Photoprism album
    upload_to_album()
