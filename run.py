"""
Example script demonstrating the complete PhotoPrism to Google Photos workflow.
This script will:
1. Download random photos from PhotoPrism
2. Resize images in the shared folder (if enabled)
3. Upload them to a dedicated album in Google Photos
4. Clean up the shared folder after successful upload
5. Run on a schedule (interval in seconds)
"""

import logging
import sys
import threading
import time
from datetime import datetime

import schedule

from config import SCHEDULER_INTERVAL_SECONDS, TOKEN_REFRESH_ΙNTERVAL_MINUTES
from downloader import PhotoPrismAPI
from resizer import resize_images
from uploader.auth import get_credentials
from uploader.main import upload_to_album
from uploader.token_manager import TokenRefreshError
from uploader.token_manager import refresh_token as refresh_google_token
from utils.alerts import AlertManager

# Configure root logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

alert_manager = AlertManager()

# Set to True when token refresh fails permanently; main loop will exit
scheduler_should_stop = False


def shutdown_scheduler():
    """Stop all scheduled jobs and signal the main loop to exit."""
    global scheduler_should_stop
    logger.critical("Shutting down scheduler due to token refresh failure")
    schedule.clear()
    scheduler_should_stop = True
    logger.info("All scheduled jobs cleared")


def download_from_photoprism():
    """Download random photos from PhotoPrism."""
    logger.info("=== Starting PhotoPrism Download ===")

    # Initialize the PhotoPrism API
    api = PhotoPrismAPI()

    # Get random albums and download photos
    selected_albums = api.get_random_albums()
    if selected_albums is not None:
        album_uids = selected_albums["uid"].tolist()
        photo_uids = api.get_album_photos(album_uids)
        logger.debug("Selected Photo UIDs:")
        logger.debug(photo_uids)

        # Download the selected photos
        downloaded_files = api.download_photos(photo_uids)
        logger.debug("Downloaded files: %s", downloaded_files)
        return True

    logger.warning("No albums or photos found in PhotoPrism")
    return False


def check_authentication():
    """Check if authentication is working properly."""
    try:
        logger.info("Checking Google Photos authentication...")
        creds = get_credentials()
        if creds and creds.valid:
            logger.info("Authentication is working properly")
            return True
        else:
            logger.warning("Authentication may have issues")
            return False
    except Exception as e:
        logger.error(f"Authentication check failed: {e}")
        return False


def upload_to_google_photos():
    """Upload photos from shared folder to Google Photos."""
    logger.info("=== Starting Google Photos Upload ===")
    upload_to_album()


def scheduled_token_refresh():
    """Refresh Google token and log outcome. On permanent failure, sends alert and shuts down scheduler."""
    logger.info("=== Scheduled Google token refresh ===")
    try:
        if refresh_google_token():
            logger.info("Google token refreshed successfully")
        else:
            logger.warning("Google token refresh failed")
    except TokenRefreshError as e:
        logger.critical("Token refresh failed permanently: %s", e)
        failure_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_manager.send_alert(
            subject="Token Refresh Failed - Manual Action Required",
            message=(
                "The Google token could not be refreshed automatically.\n\n"
                "All scheduled jobs (workflow and token refresh) have been stopped.\n\n"
                "Action required: Run the following to create a new token (browser will open):\n"
                "  python -m uploader.token_manager generate\n\n"
                f"Failure time: {failure_time}\n"
                f"Error: {e}"
            ),
            methods=["telegram"],
        )
        shutdown_scheduler()
        sys.exit(1)
    except Exception as e:
        logger.error("Error during token refresh: %s", e)


def run_in_thread(job_func, *args, **kwargs):
    """Run a scheduled job in a background thread to avoid blocking other jobs."""
    thread = threading.Thread(target=job_func, args=args, kwargs=kwargs, daemon=True)
    thread.start()


def run_workflow():
    """Run the complete PhotoPrism to Google Photos workflow."""
    try:
        logger.info("Starting PhotoPrism to Google Photos workflow...")

        # Step 0: Check authentication (optional health check)
        if not check_authentication():
            logger.error("Authentication check failed. Aborting workflow.")
            return

        # Step 1: Download from PhotoPrism
        if download_from_photoprism():
            # Wait a moment to ensure all files are written
            time.sleep(2)

            # Step 2: Resize images (if enabled)
            resize_stats = resize_images()
            if resize_stats:
                logger.info("Resize step: %s", resize_stats)

            # Step 3: Upload to Google Photos
            upload_to_google_photos()
        else:
            logger.warning("Download failed or no photos found. Skipping upload.")

        logger.info("Workflow complete!")

    except Exception as e:
        logger.error("An error occurred during the workflow: %s", str(e))
        import traceback

        logger.error(traceback.format_exc())


def main():
    """
    Run the workflow on a schedule.
    The interval is configured via SCHEDULER_INTERVAL_SECONDS environment variable.
    """
    logger.info(f"Starting scheduler. Will run every {SCHEDULER_INTERVAL_SECONDS} seconds.....")

    # Run once immediately on startup (in background to avoid blocking other schedules)
    run_in_thread(run_workflow)

    # Schedule the jobs (run in background threads so they don't block each other)
    schedule.every(SCHEDULER_INTERVAL_SECONDS).seconds.do(run_in_thread, run_workflow)
    logger.info(f"Scheduled run_workflow every {SCHEDULER_INTERVAL_SECONDS} seconds")
    # Schedule token refresh every 30 minutes (user-adjustable for testing)
    schedule.every(TOKEN_REFRESH_ΙNTERVAL_MINUTES).minutes.do(run_in_thread, scheduled_token_refresh)
    logger.info("Scheduled scheduled_token_refresh every {TOKEN_REFRESH_ΙNTERVAL_MINUTES} minutes")

    # Keep the script running
    while True:
        try:
            if scheduler_should_stop:
                logger.critical("Scheduler stopped. Exiting.")
                sys.exit(1)
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal. Exiting gracefully...")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error in scheduler loop: {str(e)}")
            time.sleep(1)  # Sleep and continue on error


if __name__ == "__main__":
    main()
