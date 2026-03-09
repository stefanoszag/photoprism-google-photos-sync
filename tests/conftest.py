"""Pytest configuration and shared fixtures."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def temp_shared_dir():
    """Create a temporary shared directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_photoprism_response():
    """Mock PhotoPrism API responses."""
    return {
        "albums": [
            {"UID": "album1", "Title": "Family Photos"},
            {"UID": "album2", "Title": "Vacation 2024"},
            {"UID": "album3", "Title": "Nature"},
        ],
        "photos": [
            {"UID": "photo1", "Title": "Photo 1"},
            {"UID": "photo2", "Title": "Photo 2"},
            {"UID": "photo3", "Title": "Photo 3"},
        ],
    }


@pytest.fixture
def mock_google_credentials():
    """Mock Google OAuth2 credentials."""
    mock_creds = Mock()
    mock_creds.valid = True
    mock_creds.expired = False
    mock_creds.token = "mock_access_token"
    mock_creds.refresh_token = "mock_refresh_token"
    return mock_creds


@pytest.fixture
def mock_google_photos_service():
    """Mock Google Photos API service."""
    mock_service = Mock()

    # Mock albums
    mock_albums = Mock()
    mock_albums.list.return_value.execute.return_value = {"albums": [{"id": "album_id_1", "title": "Photoprism"}]}
    mock_albums.create.return_value.execute.return_value = {"id": "new_album_id", "title": "Photoprism"}
    mock_service.albums.return_value = mock_albums

    # Mock media items
    mock_media = Mock()
    mock_media.batchCreate.return_value.execute.return_value = {
        "newMediaItemResults": [{"status": {"message": "Success"}, "mediaItem": {"id": "media_id_1"}}]
    }
    mock_media.search.return_value.execute.return_value = {"mediaItems": []}
    mock_service.mediaItems.return_value = mock_media

    return mock_service


@pytest.fixture
def sample_album_whitelist(tmp_path):
    """Create a sample album whitelist CSV file."""
    whitelist_file = tmp_path / "album_whitelist.csv"
    whitelist_file.write_text("album_title\n" "Family Photos\n" "Vacation 2024\n" "Nature\n")
    return whitelist_file


@pytest.fixture
def mock_requests_response():
    """Mock requests.Response object."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_response.headers = {"Content-Disposition": 'filename="test.jpg"'}
    mock_response.iter_content = lambda chunk_size: [b"fake_image_data"]
    return mock_response
