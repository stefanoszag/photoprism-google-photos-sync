#!/usr/bin/env python3
"""Token management utility for Google Photos API authentication.

This script helps manage authentication tokens for remote deployment scenarios.
"""

import logging
import os
import sys
from datetime import datetime, timezone

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import CREDENTIALS_FILE, SCOPES, TOKEN_FILE

# Configure logger
logger = logging.getLogger(__name__)


class TokenRefreshError(Exception):
    """Raised when token refresh fails permanently and requires manual re-authentication."""

    pass


def check_token_status():
    """Check the status of the current token."""
    if not os.path.exists(TOKEN_FILE):
        logger.error(f"Token file not found: {TOKEN_FILE}")
        return False

    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        logger.info(f"Token file: {TOKEN_FILE}")
        logger.info(f"Has refresh token: {'Refreshed' if creds.refresh_token else 'Not refreshed'}")
        logger.info(f"Token valid: {'Valid' if creds.valid else 'Not valid'}")

        if hasattr(creds, "expiry") and creds.expiry:
            expiry = creds.expiry.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            time_left = expiry - now

            if time_left.total_seconds() > 0:
                logger.info(f"Expires in: {time_left}")
            else:
                logger.warning(f"Expired: {time_left} ago")

        if creds.expired and creds.refresh_token:
            logger.info("Token expired but refresh token available - can auto-refresh")
        elif creds.expired and not creds.refresh_token:
            logger.error("Token expired and no refresh token - manual re-auth required")

        return True

    except Exception as e:
        logger.error(f"Error reading token file: {e}")
        return False


def _is_permanent_refresh_failure(error: Exception) -> bool:
    """Return True if the error indicates permanent failure requiring manual re-auth."""
    msg = str(error).lower()
    return "invalid_grant" in msg or "token has been expired or revoked" in msg or "revoked" in msg and "token" in msg


def refresh_token():
    """Attempt to refresh the current token.

    Raises:
        TokenRefreshError: When refresh fails permanently (e.g. invalid_grant, no refresh token).
    """
    if not os.path.exists(TOKEN_FILE):
        logger.error(f"Token file not found: {TOKEN_FILE}")
        raise TokenRefreshError(f"Token file not found: {TOKEN_FILE}") from None

    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds.refresh_token:
            logger.error("No refresh token available")
            raise TokenRefreshError(
                "No refresh token available. Run 'python -m uploader.token_manager generate' to create a new token."
            ) from None

        logger.info("Refreshing token...")
        creds.refresh(Request())

        # Save refreshed token
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

        logger.info("Token refreshed successfully")
        return True

    except TokenRefreshError:
        raise
    except RefreshError as e:
        if _is_permanent_refresh_failure(e):
            logger.error(f"Failed to refresh token (permanent): {e}")
            raise TokenRefreshError(str(e)) from e
        logger.error(f"Failed to refresh token: {e}")
        return False
    except Exception as e:
        if _is_permanent_refresh_failure(e):
            logger.error(f"Failed to refresh token (permanent): {e}")
            raise TokenRefreshError(str(e)) from e
        logger.error(f"Failed to refresh token: {e}")
        return False


def generate_new_token():
    """Generate a new token through OAuth flow."""
    if not os.path.exists(CREDENTIALS_FILE):
        logger.error(f"Credentials file not found: {CREDENTIALS_FILE}")
        logger.error("Please download credentials.json from Google Cloud Console")
        return False

    try:
        logger.info("Starting OAuth flow...")
        logger.info("This will open a browser window for authentication")

        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

        # Save the credentials
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

        logger.info(f"New token saved to {TOKEN_FILE}")
        return True

    except Exception as e:
        logger.error(f"Failed to generate new token: {e}")
        return False


def validate_token_for_remote():
    """Validate that the token is suitable for remote deployment."""
    if not check_token_status():
        return False

    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds.refresh_token:
            logger.error("Token not suitable for remote deployment - no refresh token")
            logger.info("Run 'python -m uploader.token_manager generate' to create a new token")
            return False

        if creds.expired:
            logger.warning("Token is expired, testing refresh capability...")
            if refresh_token():
                logger.info("Token is suitable for remote deployment")
                return True
            else:
                logger.error("Token refresh failed - not suitable for remote deployment")
                return False
        else:
            logger.info("Token is valid and suitable for remote deployment")
            return True

    except Exception as e:
        logger.error(f"Error validating token: {e}")
        return False


def main():
    """Main CLI interface."""
    if len(sys.argv) < 2:
        logger.info("Usage: python -m uploader.token_manager <command>")
        logger.info("Commands:")
        logger.info("  status    - Check current token status")
        logger.info("  refresh   - Refresh the current token")
        logger.info("  generate  - Generate a new token (requires browser)")
        logger.info("  validate  - Validate token for remote deployment")
        return

    command = sys.argv[1].lower()

    if command == "status":
        check_token_status()
    elif command == "refresh":
        refresh_token()
    elif command == "generate":
        generate_new_token()
    elif command == "validate":
        validate_token_for_remote()
    else:
        logger.error(f"Unknown command: {command}")


if __name__ == "__main__":
    # Configure logging for CLI usage
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    main()
