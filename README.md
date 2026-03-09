# PhotoPrism Google Home Integration

![Docker](https://img.shields.io/badge/docker-available-2496ED?logo=docker)
![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Build Status](https://github.com/stefanoszag/photoprism-google-photos-sync/workflows/Docker%20Build%20and%20Push/badge.svg)
[![codecov](https://codecov.io/gh/stefanoszag/photoprism-google-photos-sync/branch/main/graph/badge.svg)](https://codecov.io/gh/stefanoszag/photoprism-google-photos-sync)
![Code Quality](https://img.shields.io/badge/code%20style-ruff-000000.svg)

**Seamlessly sync your self-hosted PhotoPrism photos to Google Photos for display on Google Home devices.**

A production-ready Python automation service that bridges the gap between self-hosted photo management and smart home ecosystems, featuring scheduled synchronization, multi-channel alerting, and automated deployment workflows.

---

## Features

- **Automated Photo Sync** - Scheduled synchronization from PhotoPrism to Google Photos with configurable intervals
- **Smart Photo Selection** - Random album and photo selection from whitelisted albums
- **Multi-Channel Alerts** - Real-time notifications via Email, Slack, and Telegram
- **OAuth2 Token Management** - Automatic token refresh for unattended operation
- **Storage Monitoring** - Track Google Drive quota with high-usage alerts
- **Configurable Image Resizing** - Optionally resize images by percentage before upload (saves storage and bandwidth)
- **Multi-Architecture Docker** - Native support for amd64 and arm64 (Raspberry Pi, Apple Silicon)
- **CI/CD Pipeline** - Automated builds and deployments via GitHub Actions
- **Self-Hosted Runner Support** - Direct deployment to LXC containers or home servers

---

## Quick Start

### Option 1: Docker (Recommended)

The fastest way to get started:

```bash
# 1. Clone the repository
git clone https://github.com/stefanoszag/photoprism-google-photos-sync.git
cd photoprism-google-photos-sync

# 2. Copy and configure environment variables
cp .env.example .env
# Edit .env with your PhotoPrism and Google Photos credentials

# 3. Set up Google Photos API credentials
# Follow instructions in docs/authentication.md to obtain credentials.json
# Place it in the uploader/ directory

# 4. Run with Docker Compose
docker-compose up -d

# 5. View logs
docker-compose logs -f
```

### Option 2: Local Installation

```bash
# 1. Clone and install dependencies
git clone https://github.com/stefanoszag/photoprism-google-photos-sync.git
cd photoprism-google-photos-sync
pip install -r requirements.txt

# 2. Configure environment variables
export PHOTOPRISM_SERVER_URL="https://your-photoprism-instance.com"
export PHOTOPRISM_USERNAME="your-username"
export PHOTOPRISM_PASSWORD="your-password"
export GOOGLE_PHOTOS_ALBUM_NAME="Photoprism"
export NUM_RANDOM_ALBUMS=3
export NUM_RANDOM_PHOTOS=10

# 3. Set up Google Photos API (see docs/authentication.md)

# 4. Run the application
python run.py
```

---

## Architecture Overview

```
  PhotoPrism          Sync Service         Google Photos       Google Home
  (self-hosted)  -->  (run.py)        -->  (album)        -->  (devices)
       |                    |
       |                    +--------->  Alerts (Email / Slack / Telegram)
       |
       +-- random photos    +-- upload    +-- display
```

The application runs as a scheduled service that:
1. **Downloads** random photos from whitelisted PhotoPrism albums
2. **Uploads** them to a dedicated Google Photos album
3. **Cleans up** local storage after successful sync
4. **Monitors** storage quota and sends alerts on issues
5. **Refreshes** authentication tokens automatically

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

---

## Use Cases

### Google Home Photo Frame
Display a rotating selection of your self-hosted photos on Google Home Hub or Nest Hub devices without manually syncing to the cloud.

### Automated Photo Backup
Periodically backup selected albums from your PhotoPrism instance to Google Photos as a secondary cloud storage.

### Smart Home Integration
Keep your Google ecosystem in sync with your privacy-focused self-hosted photo library.

### Random Photo Displays
Curate dynamic photo albums that automatically refresh with new random selections from your collection.

---

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `PHOTOPRISM_SERVER_URL` | Your PhotoPrism instance URL | Yes | - |
| `PHOTOPRISM_USERNAME` | PhotoPrism username | Yes | - |
| `PHOTOPRISM_PASSWORD` | PhotoPrism password | Yes | - |
| `GOOGLE_PHOTOS_ALBUM_NAME` | Target album name in Google Photos | Yes | - |
| `NUM_RANDOM_ALBUMS` | Number of albums to select photos from | Yes | - |
| `NUM_RANDOM_PHOTOS` | Total number of photos to sync | Yes | - |
| `SCHEDULER_INTERVAL_SECONDS` | Sync interval in seconds | No | 86400 (24h) |
| `RESIZE_ENABLED` | Resize images before upload | No | false |
| `RESIZE_PERCENTAGE` | Resize to this % of original dimensions (e.g. 80) | No | 100 |

**Optional Alert Configuration:**

| Variable | Description |
|----------|-------------|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL` | Email alerts |
| `SLACK_WEBHOOK_URL` | Slack notifications |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram alerts |

See [`.env.example`](.env.example) for a complete configuration template.

### Image Resizing

You can optionally resize images before they are uploaded to Google Photos. This reduces storage usage and upload time.

- **`RESIZE_ENABLED`** – Set to `true` to enable resizing. Default: `false`.
- **`RESIZE_PERCENTAGE`** – Scale images to this percentage of their original width and height (aspect ratio is preserved). For example, `80` resizes a 4000×3000 image to 3200×2400. Use `100` to keep original size. Default: `100`.

Images are resized in place in the shared folder after download and before upload. Original formats (JPEG, PNG, etc.) are preserved.

### Album Whitelist

Configure which PhotoPrism albums to include in the random selection:

Edit `downloader/data/album_whitelist.csv`:
```csv
album_title
Family Photos
Vacation 2024
Nature
Best of 2023
```

Only albums listed here will be considered for photo selection.

---

## Project Structure

```
.
├── downloader/              # PhotoPrism download functionality
│   ├── main.py             # PhotoPrism API client
│   ├── auth.py             # Authentication utilities
│   ├── config.py           # Configuration settings
│   └── data/
│       └── album_whitelist.csv  # Album selection whitelist
├── uploader/               # Google Photos upload functionality
│   ├── main.py             # Google Photos API client
│   ├── auth.py             # OAuth2 authentication
│   ├── token_manager.py    # Token lifecycle management
│   └── config.py           # Configuration settings
├── resizer/                # Image resizing before upload
│   ├── main.py             # Resize logic (Pillow)
│   └── config.py           # RESIZE_ENABLED, RESIZE_PERCENTAGE
├── docs/                   # Documentation
│   ├── architecture.md     # System architecture and design
│   ├── authentication.md   # Google Photos API setup guide
│   ├── deployment.md       # Docker deployment instructions
│   └── self-hosted-runner.md  # CI/CD setup guide
├── tests/                  # Test suite (pytest)
├── run.py                  # Main workflow orchestrator
├── utils/                  # Shared utilities
│   └── alerts.py           # Multi-channel alert system
├── config.py               # Global configuration
├── Dockerfile              # Multi-arch container image
├── docker-compose.yml      # Container orchestration
└── requirements.txt        # Python dependencies
```

---

## Documentation

- [Architecture Overview](docs/architecture.md) - System design, data flow, and component breakdown
- [Authentication Guide](docs/authentication.md) - Setting up Google Photos API access
- [Deployment Guide](docs/deployment.md) - Docker deployment and container management
- [Self-Hosted Runner Setup](docs/self-hosted-runner.md) - CI/CD automation configuration

---

## Development

### Running Tests

Use the same command as CI so coverage matches [GitHub Actions](.github/workflows/docker-build.yml):

```bash
# Install development dependencies
pip install -r requirements.txt

# Run test suite (same as CI)
pytest tests/ -v --cov=. --cov-report=term --cov-report=html --tb=short

# Optional: also show missing lines per file
pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html --tb=short
```

Coverage includes `config.py`, `run.py`, `downloader/`, `uploader/`, and `utils/`. If you see different totals locally (e.g. lower downloader coverage), ensure all tests run—on some macOS setups `test_downloader.py` can segfault (numpy/pandas); CI on Ubuntu runs all tests.

### Code Quality

This project uses pre-commit hooks to maintain code quality:

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

### Local Development

```bash
# Run in development mode (single execution)
python run.py

# Test individual components
python -m downloader.main  # Test PhotoPrism downloader
python -m uploader.main     # Test Google Photos uploader

# Check authentication status
python -m uploader.token_manager status
```

---

## Deployment

### Docker Hub

Pre-built multi-architecture images are available:

```bash
docker pull stefanoszag/photoprism-google-photos-sync:latest
```

Supports:
- `linux/amd64` - Standard x86_64 servers
- `linux/arm64` - Raspberry Pi, ARM servers, Apple Silicon

### Automated Deployment

The project includes a complete CI/CD pipeline:

1. **Build** - Multi-arch Docker images built on every push to main
2. **Publish** - Automatically pushed to Docker Hub
3. **Deploy** - Self-hosted runner pulls and restarts containers

See [docs/deployment.md](docs/deployment.md) and [docs/self-hosted-runner.md](docs/self-hosted-runner.md) for setup instructions.

---

## Monitoring

### Logs

```bash
# Docker logs
docker-compose logs -f

# Filter by log level
docker-compose logs -f | grep ERROR
```

### Alerts

The application sends alerts for:
- High storage usage (>95% of Google Drive quota)
- Upload failures with file details
- Authentication issues
- Execution summaries with statistics

Configure alert channels via environment variables.

### Token Management

```bash
# Check token status
docker-compose exec photoprism-google-photos-sync python -m uploader.token_manager status

# Manually refresh token
docker-compose exec photoprism-google-photos-sync python -m uploader.token_manager refresh

# Validate for remote deployment
docker-compose exec photoprism-google-photos-sync python -m uploader.token_manager validate
```

---

## Troubleshooting

### Common Issues

**Problem:** "No albums found in PhotoPrism"
- Verify album names in `album_whitelist.csv` match PhotoPrism exactly (case-sensitive)
- Check PhotoPrism authentication credentials

**Problem:** "Refresh token invalid"
- Regenerate token: `python -m uploader.token_manager generate`
- Ensure `credentials.json` is correctly configured

**Problem:** "Storage quota exceeded"
- Check Google Drive storage: `python -m uploader.token_manager status`
- Free up space or upgrade Google One storage plan

**Problem:** Container stops unexpectedly
- Check logs: `docker-compose logs`
- Verify all required environment variables are set
- Ensure credentials files are mounted correctly

For more troubleshooting guidance, see [docs/architecture.md](docs/architecture.md#troubleshooting).

---

## Security

- All credentials stored in environment variables or mounted files (never in code)
- Google OAuth2 tokens automatically refreshed
- Sensitive files excluded via `.gitignore`
- Docker volumes can be mounted read-only where appropriate
- HTTPS used for all API communications

---

## Contributing

Contributions are welcome! This project serves as a portfolio piece but is open to improvements.

**Areas for Contribution:**
- Additional cloud storage providers (Dropbox, OneDrive, etc.)
- Web UI for configuration and monitoring
- Photo deduplication logic
- Video file support
- Incremental sync (track uploaded photos)
- Performance optimizations

Please ensure:
- Code follows existing style (ruff/black formatting)
- Tests pass (`pytest`)
- Pre-commit hooks pass
- Documentation is updated

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Acknowledgments

Built with:
- [PhotoPrism](https://photoprism.app/) - Self-hosted photo management
- [Google Photos API](https://developers.google.com/photos) - Cloud photo storage
- Python 3.9+ ecosystem

---

## Author

**Stefanos Zagkotas**

This project demonstrates:
- Production-ready Python application design
- Docker containerization and multi-arch builds
- CI/CD pipeline automation with GitHub Actions
- OAuth2 authentication and token management
- REST API integration (PhotoPrism, Google Photos)
- Multi-channel alerting systems
- Automated deployment workflows

---

## Support

- **Issues:** [GitHub Issues](https://github.com/stefanoszag/photoprism-google-photos-sync/issues)
- **Discussions:** [GitHub Discussions](https://github.com/stefanoszag/photoprism-google-photos-sync/discussions)
- **Documentation:** [docs/](docs/)

For questions about setup or configuration, please open a discussion rather than an issue.
