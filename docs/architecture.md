# System Architecture

## Overview

PhotoPrism Google Home Integration is a Python-based automation service that bridges PhotoPrism (self-hosted photo management) with Google Photos, enabling seamless photo synchronization for Google Home devices to display.

## High-Level Architecture

```
  EXTERNAL SERVICES              APPLICATION CONTAINER                    ALERT CHANNELS
  -----------------              --------------------                    ---------------
  PhotoPrism Server  ----REST---->  Downloader Module  ----photos---->    Email / SMTP
  (self-hosted)                      (PhotoPrism API)        |            Slack Webhook
       |                                    |                 v            Telegram Bot
       |                                    v            Shared Storage
       |                            Scheduler  ----------> (temp cache)
       |                                    |                 |
       |                                    v                 v
  Google Photos API  <---upload-----  Uploader Module  <---read photos---
  (cloud storage)       (OAuth2)      (Google Photos API)
                                |
                                +-----> Authentication Manager (token refresh)
                                +-----> Alert System ------> Email, Slack, Telegram
```

## Component Breakdown

### 1. Scheduler (`run.py`)

**Purpose:** Orchestrates the complete workflow on a configurable schedule.

**Key Features:**
- Configurable execution interval via `SCHEDULER_INTERVAL_SECONDS`
- Background threading to prevent blocking
- Automatic token refresh every 30 minutes
- Graceful error handling and recovery
- Health check authentication before workflow execution

**Workflow Execution:**
1. Check Google Photos authentication status
2. Trigger downloader to fetch photos from PhotoPrism
3. Wait for downloads to complete
4. Trigger uploader to sync to Google Photos
5. Send execution summary via alert system

### 2. Downloader Module (`downloader/`)

**Purpose:** Interfaces with PhotoPrism API to select and download random photos from whitelisted albums.

**Components:**
- `main.py` - PhotoPrism API client implementation
- `auth.py` - PhotoPrism authentication utilities
- `config.py` - Downloader-specific configuration
- `data/album_whitelist.csv` - Album selection whitelist

**Key Features:**
- Album whitelist management (CSV-based)
- Random album selection (`NUM_RANDOM_ALBUMS`)
- Random photo selection from albums (`NUM_RANDOM_PHOTOS`)
- Automatic directory cleanup before downloads
- Comprehensive error handling and logging

**API Endpoints Used:**
- `GET /api/v1/albums` - List all albums
- `GET /api/v1/photos?s={album_uid}` - Get photos in album
- `GET /api/v1/photos/{uid}/dl` - Download photo

### 3. Uploader Module (`uploader/`)

**Purpose:** Manages Google Photos integration with OAuth2 authentication and photo upload.

**Components:**
- `main.py` - Google Photos API client implementation
- `auth.py` - OAuth2 credential management
- `token_manager.py` - Token lifecycle utilities
- `config.py` - Uploader-specific configuration

**Key Features:**
- OAuth2 authentication with automatic token refresh
- Album creation and management
- Batch photo upload (via upload token mechanism)
- Album cleanup (remove old photos before new upload)
- Storage quota monitoring with alerts
- Automatic cleanup of local files after successful upload

**Authentication Flow:**

```
  App          auth.py      token_manager.py    Google OAuth2
   |              |                |                    |
   |-- Request credentials ------->|                    |
   |              |                |-- Check token --->|
   |              |                |                    |
   |              |     [Token valid?]                  |
   |              |         |-- Yes --> Return credentials to App
   |              |         |
   |              |     [Token expired?]
   |              |         |-- Yes --> Refresh request --> Google
   |              |         |                <-- New access token
   |              |         |                --> Return to App
   |              |         |
   |              |     [No token?]
   |              |         |-- Yes --> OAuth2 flow --> Google
   |              |         |                <-- Access + Refresh tokens
   |              |         |                --> Return to App
```

### 4. Alert System (`utils/alerts.py`)

**Purpose:** Multi-channel notification system for workflow events, errors, and monitoring.

**Supported Channels:**
- **Email (SMTP)** - Full execution summaries, critical errors
- **Slack** - Webhook-based notifications
- **Telegram** - Bot-based real-time alerts

**Alert Types:**
- High storage usage warnings (>95%)
- Upload failures with file details
- Album cleanup failures
- Shared folder cleanup issues
- Critical errors with stack traces
- Execution summaries with statistics

**Example Alert Content:**
- Start/end times and duration
- Upload statistics (total, successful, failed)
- Storage usage (before/after)
- Warnings and errors with context

### 5. Shared Storage (`shared/`)

**Purpose:** Temporary local storage for photos in transit between PhotoPrism and Google Photos.

**Lifecycle:**
1. Created on application startup if not exists
2. Cleaned before each download batch
3. Populated with downloaded photos
4. Photos uploaded to Google Photos
5. Cleaned after successful uploads (keeps files if any upload fails)

**Security:** Directory is gitignored to prevent credential/photo leakage.

## Data Flow

### Complete Workflow Sequence

```
  1. Scheduler waits for interval, then:
     - Health check: Uploader -> Google Photos (verify credentials)

  2. Download workflow:
     Scheduler -> Downloader: Start
     Downloader: Read whitelist -> Get albums from PhotoPrism -> Select random albums/photos
     Downloader -> Shared: Clean dir, then for each photo: Download from PhotoPrism -> Save to Shared

  3. Upload workflow:
     Scheduler -> Uploader: Start
     Uploader -> Google Photos: Check quota (if high -> Alerts)
     Uploader -> Google Photos: Get or create album
     Uploader -> Google Photos: Remove existing photos from album
     For each photo in Shared:
       Uploader -> Google Photos: Upload bytes -> Create media item in album
     Uploader -> Google Photos: Check quota again

  4. Cleanup:
     If all uploads OK: Delete photos from Shared
     If any failed: Keep photos, send failure alert
     Uploader -> Alerts: Send execution summary (Email/Slack/Telegram)
```

## Configuration

### Environment Variables

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `PHOTOPRISM_SERVER_URL` | PhotoPrism instance URL | - | Yes |
| `PHOTOPRISM_USERNAME` | PhotoPrism username | - | Yes |
| `PHOTOPRISM_PASSWORD` | PhotoPrism password | - | Yes |
| `GOOGLE_PHOTOS_ALBUM_NAME` | Target album in Google Photos | - | Yes |
| `NUM_RANDOM_ALBUMS` | Albums to select photos from | - | Yes |
| `NUM_RANDOM_PHOTOS` | Total photos to sync | - | Yes |
| `SCHEDULER_INTERVAL_SECONDS` | Workflow execution interval | 86400 | No |
| `SMTP_HOST` | Email server host | smtp.gmail.com | No |
| `SMTP_PORT` | Email server port | 587 | No |
| `SMTP_USER` | Email username | - | No |
| `SMTP_PASSWORD` | Email password/app token | - | No |
| `ALERT_EMAIL` | Alert recipient email | - | No |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | - | No |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | - | No |
| `TELEGRAM_CHAT_ID` | Telegram chat ID | - | No |

### File-based Configuration

**Album Whitelist** (`downloader/data/album_whitelist.csv`):
```csv
album_title
Family Photos
Vacation 2024
Nature
```

Only albums listed here will be considered for random selection.

## Deployment Architecture

### Docker Container

```
  DOCKER HOST (LXC / server)
  --------------------------
  +------------------+     +---------------------------+
  | Application      |     | Mounted Volumes           |
  | - run.py         |<--->| - credentials.json (ro)  |
  | - requirements   |     | - token.json (rw)        |
  |                  |     | - album_whitelist (opt)   |
  +------------------+     +---------------------------+

  GITHUB ACTIONS CI/CD
  --------------------
  Push to main --> Build (linux/amd64) --> Push to Docker Hub
       --> Self-hosted runner --> docker-compose pull --> Restart container
```

**Build Process:**
- Single-architecture image (linux/amd64) for LXC deployment
- Published to Docker Hub: `stefanoszag/photoprism-google-sync:latest`
- Automated via GitHub Actions on main branch push
- Auto-deployment to LXC container via self-hosted runner

**Docker Image Optimizations:**
- **Multi-stage build:** Builder stage installs dependencies (including gcc); runtime stage copies only the virtual env and app code. Build tools and test dependencies are not in the final image, reducing size.
- **Security:** Only runtime dependencies and application code are included; no build tools in the final image.
- **Layer caching:** Dependencies are installed in a separate layer; application code is copied last so code-only changes rebuild quickly.
- **Runtime-only deps:** Test and dev packages (pytest, mypy, etc.) are excluded from the production image.

### Production Deployment

**Recommended Setup:**
1. Proxmox LXC container with Docker installed
2. Self-hosted GitHub Actions runner for CD
3. Docker Compose for container orchestration
4. Volume mounts for credentials and configuration
5. Restart policy: `unless-stopped`

## Security Considerations

### Credential Management

1. **PhotoPrism Credentials** - Stored as environment variables, never committed
2. **Google OAuth2 Credentials** - `credentials.json` mounted as read-only volume
3. **OAuth2 Tokens** - `token.json` persisted across restarts, automatically refreshed
4. **Secrets in Git** - All sensitive files in `.gitignore`

### API Permissions

**PhotoPrism:**
- Read-only access to albums and photos
- Download permission for photo files

**Google Photos:**
- OAuth scopes: `photoslibrary` (full access)
- Required for album creation, photo upload, and photo removal

### Network Security

- No exposed ports (outbound-only connections)
- HTTPS for all API communications
- Secure token storage with automatic refresh

## Monitoring and Observability

### Logging

**Log Levels:**
- INFO: Workflow progress, successful operations
- WARNING: Non-critical issues (missing albums, high storage)
- ERROR: Upload failures, API errors
- DEBUG: Detailed API responses, file operations

**Log Format:**
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### Alerting

**Trigger Conditions:**
- Storage >95% usage
- Upload failures (any)
- Album cleanup failures
- Critical errors with stack traces
- Execution summary (always)

### Metrics

**Tracked per Execution:**
- Photos downloaded
- Photos uploaded (success/failure)
- Storage usage (before/after)
- Execution duration
- Errors and warnings

## Scalability Considerations

### Current Limitations

1. **Sequential Processing** - Photos processed one at a time
2. **Single Album Target** - All photos go to one Google Photos album
3. **No Persistent State** - No database, stateless operation
4. **API Rate Limits** - Subject to PhotoPrism and Google Photos API limits

### Potential Improvements

1. **Parallel Downloads/Uploads** - Use threading or async for concurrent operations
2. **Multiple Album Support** - Map PhotoPrism albums to separate Google Photos albums
3. **State Management** - Track uploaded photos to avoid duplicates
4. **Retry Logic** - Exponential backoff for failed uploads
5. **Batch Operations** - Group uploads for better efficiency

## Technology Stack

- **Language:** Python 3.9+
- **Web Frameworks:** None (API clients only)
- **HTTP Client:** `requests`
- **Data Processing:** `pandas` (album/photo selection)
- **Authentication:** `google-auth`, `google-auth-oauthlib`
- **Google APIs:** `google-api-python-client`
- **Scheduling:** `schedule` library
- **Containerization:** Docker (linux/amd64)
- **CI/CD:** GitHub Actions
- **Deployment:** Docker Compose

## Troubleshooting

### Common Issues

**Issue:** "Refresh token invalid"
**Solution:** Regenerate token using `python -m uploader.token_manager generate`

**Issue:** "No albums found in PhotoPrism"
**Solution:** Check `album_whitelist.csv` and verify album titles match PhotoPrism exactly

**Issue:** "Storage quota exceeded"
**Solution:** Free up space in Google Drive or upgrade storage plan

**Issue:** "Container stops unexpectedly"
**Solution:** Check logs with `docker-compose logs -f` for detailed error messages

### Debug Commands

```bash
# Check token status
python -m uploader.token_manager status

# Test token refresh
python -m uploader.token_manager refresh

# Validate remote deployment readiness
python -m uploader.token_manager validate

# View container logs
docker-compose logs -f

# Check storage quota
# (Automatically logged during upload workflow)
```

## Future Roadmap

- [ ] Add photo deduplication logic
- [ ] Support multiple Google Photos albums
- [ ] Implement retry mechanism with exponential backoff
- [ ] Add web UI for configuration and monitoring
- [ ] Support additional cloud storage providers
- [ ] Add photo metadata preservation
- [ ] Implement incremental sync (track uploaded photos)
- [ ] Add Prometheus metrics export
- [ ] Support video files in addition to photos
