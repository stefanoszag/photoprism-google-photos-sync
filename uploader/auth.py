"""Authentication module for Google Photos API."""

import logging
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import CREDENTIALS_FILE, SCOPES, TOKEN_FILE

# Configure logger
logger = logging.getLogger(__name__)


def get_credentials():
    """Get valid user credentials from storage.

    If no valid credentials are found, the user will be prompted to log in.
    For remote deployments, ensure a valid token.json with refresh_token is available.
    """
    creds = None

    # Check if token file exists
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            logger.error(f"Error loading credentials from {TOKEN_FILE}: {e}")
            creds = None

    # If no valid credentials available, try to refresh or prompt for login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Token expired, attempting to refresh...")
                creds.refresh(Request())
                logger.info("Token refreshed successfully")

                # Save the refreshed credentials
                with open(TOKEN_FILE, "w") as token:
                    token.write(creds.to_json())
                logger.info(f"Refreshed token saved to {TOKEN_FILE}")

            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                logger.warning("Refresh token may be invalid or expired")
                creds = None

        # If refresh failed or no refresh token available, need new authentication
        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Missing credentials file. Please download {CREDENTIALS_FILE} "
                    "from Google Cloud Console and place it in the current directory."
                )

            logger.warning("No valid credentials found. Starting OAuth flow...")
            logger.warning("This requires browser interaction and is not suitable for remote deployment.")
            logger.warning("For remote deployment, ensure you have a valid token.json with refresh_token.")

            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
            logger.info(f"New token saved to {TOKEN_FILE}")

    return creds
