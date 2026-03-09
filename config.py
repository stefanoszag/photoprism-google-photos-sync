"""Configuration settings for the PhotoPrism to Google Photos workflow."""

import os

# Scheduler settings
SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "86400"))

# Token refresh interval settings
TOKEN_REFRESH_ΙNTERVAL_MINUTES = int(os.getenv("TOKEN_REFRESH_ΙNTERVAL_MINUTES", "50"))
