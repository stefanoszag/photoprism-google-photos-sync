"""Tests for the PhotoPrism downloader module."""

from unittest.mock import Mock, patch

import pandas as pd
import pytest
import requests


@pytest.fixture
def mock_photoprism_api():
    """Create a mock PhotoPrism API instance."""
    with patch("downloader.auth.get_token", return_value="mock_token"):
        from downloader.main import PhotoPrismAPI

        api = PhotoPrismAPI()
        return api


class TestPhotoPrismAPI:
    """Test suite for PhotoPrism API client."""

    def test_initialization(self, mock_photoprism_api):
        """Test PhotoPrismAPI initialization."""
        assert mock_photoprism_api.token == "mock_token"
        assert "Authorization" in mock_photoprism_api.headers
        assert mock_photoprism_api.headers["Authorization"] == "Bearer mock_token"

    @patch("requests.get")
    def test_get_albums_success(self, mock_get, mock_photoprism_api, mock_photoprism_response):
        """Test successful album retrieval."""
        mock_get.return_value.json.return_value = mock_photoprism_response["albums"]
        mock_get.return_value.raise_for_status = Mock()

        albums = mock_photoprism_api.get_albums()

        assert albums is not None
        assert len(albums) == 3
        assert albums[0]["Title"] == "Family Photos"

    @patch("requests.get")
    def test_get_albums_failure(self, mock_get, mock_photoprism_api):
        """Test album retrieval failure."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        albums = mock_photoprism_api.get_albums()

        assert albums is None

    @patch("requests.get")
    def test_get_albums_http_error_with_response_text(self, mock_get, mock_photoprism_api):
        """Test get_albums when HTTP error includes response text (covers logger.error branch)."""
        err = requests.exceptions.HTTPError("401 Unauthorized")
        err.response = Mock()
        err.response.text = '{"error": "invalid credentials"}'
        mock_get.return_value.raise_for_status.side_effect = err

        albums = mock_photoprism_api.get_albums()

        assert albums is None

    @patch("downloader.main.PhotoPrismAPI.get_albums")
    @patch("downloader.main.pd.read_csv")
    def test_process_whitelist(self, mock_read_csv, mock_get_albums, mock_photoprism_api, mock_photoprism_response):
        """Test whitelist processing."""
        # Mock whitelist CSV
        mock_df = pd.DataFrame({"album_title": ["Family Photos", "Vacation 2024", "Missing Album"]})
        mock_read_csv.return_value = mock_df

        # Mock albums response
        mock_get_albums.return_value = mock_photoprism_response["albums"]

        result = mock_photoprism_api.process_whitelist()

        assert result is not None
        assert "uid" in result.columns
        assert len(result) == 3
        # Check that two albums were found
        assert result["uid"].notna().sum() == 2

    @patch("downloader.main.PhotoPrismAPI.get_albums")
    @patch("downloader.main.pd.read_csv")
    def test_process_whitelist_returns_none_when_get_albums_fails(
        self, mock_read_csv, mock_get_albums, mock_photoprism_api
    ):
        """Test process_whitelist returns None when get_albums returns None."""
        mock_read_csv.return_value = pd.DataFrame({"album_title": ["Some Album"]})
        mock_get_albums.return_value = None

        result = mock_photoprism_api.process_whitelist()

        assert result is None

    @patch("downloader.main.PhotoPrismAPI.process_whitelist")
    @patch("downloader.config.NUM_RANDOM_ALBUMS", 2)
    def test_get_random_albums(self, mock_process_whitelist, mock_photoprism_api):
        """Test random album selection."""
        # Mock whitelist with UIDs
        mock_df = pd.DataFrame(
            {"album_title": ["Family Photos", "Vacation 2024", "Nature"], "uid": ["album1", "album2", "album3"]}
        )
        mock_process_whitelist.return_value = mock_df

        result = mock_photoprism_api.get_random_albums()

        assert result is not None
        assert len(result) == 2
        assert "uid" in result.columns

    @patch("downloader.main.PhotoPrismAPI.process_whitelist")
    def test_get_random_albums_returns_none_when_process_whitelist_fails(
        self, mock_process_whitelist, mock_photoprism_api
    ):
        """Test get_random_albums returns None when process_whitelist returns None."""
        mock_process_whitelist.return_value = None

        result = mock_photoprism_api.get_random_albums()

        assert result is None

    @patch("requests.get")
    def test_get_album_photos(self, mock_get, mock_photoprism_api, mock_photoprism_response):
        """Test photo retrieval from albums."""
        mock_get.return_value.json.return_value = mock_photoprism_response["photos"]
        mock_get.return_value.raise_for_status = Mock()

        photo_uids = mock_photoprism_api.get_album_photos(["album1", "album2"])

        assert photo_uids is not None
        assert isinstance(photo_uids, list)

    @patch("requests.get")
    def test_get_album_photos_request_error_with_response_text(self, mock_get, mock_photoprism_api):
        """Test get_album_photos when one album request fails with response text."""
        err = requests.exceptions.HTTPError("500 Server Error")
        err.response = Mock()
        err.response.text = "Internal error"
        ok_response = Mock()
        ok_response.json.return_value = [{"UID": "p1"}, {"UID": "p2"}]
        ok_response.raise_for_status = Mock()
        mock_get.side_effect = [err, ok_response]

        photo_uids = mock_photoprism_api.get_album_photos(["album1", "album2"])

        assert photo_uids == ["p1", "p2"]

    @patch("downloader.config.NUM_RANDOM_PHOTOS", 10)
    @patch("requests.get")
    def test_get_album_photos_fewer_photos_than_requested(self, mock_get, mock_photoprism_api):
        """Test get_album_photos returns all photos when fewer than NUM_RANDOM_PHOTOS."""
        mock_get.return_value.json.return_value = [{"UID": "a"}, {"UID": "b"}]
        mock_get.return_value.raise_for_status = Mock()

        photo_uids = mock_photoprism_api.get_album_photos(["album1"])

        assert photo_uids == ["a", "b"]

    @patch("requests.get")
    @patch("builtins.open", create=True)
    def test_download_photos(self, mock_open, mock_get, mock_photoprism_api, temp_shared_dir, mock_requests_response):
        """Test photo download."""
        mock_photoprism_api.photos_dir = temp_shared_dir
        mock_get.return_value = mock_requests_response

        photo_uids = ["photo1", "photo2"]
        downloaded_files = mock_photoprism_api.download_photos(photo_uids)

        assert isinstance(downloaded_files, list)
        assert len(downloaded_files) >= 0

    @patch("requests.get")
    @patch("builtins.open", create=True)
    def test_download_photos_request_error_with_response_text(
        self, mock_open, mock_get, mock_photoprism_api, temp_shared_dir, mock_requests_response
    ):
        """Test download_photos when one request fails with response text (covers logger branch)."""
        mock_photoprism_api.photos_dir = temp_shared_dir
        err = requests.exceptions.HTTPError("404")
        err.response = Mock()
        err.response.text = "Not found"
        mock_get.side_effect = [err, mock_requests_response]

        downloaded_files = mock_photoprism_api.download_photos(["uid1", "uid2"])

        assert len(downloaded_files) == 1

    def test_clean_photos_directory(self, mock_photoprism_api, temp_shared_dir):
        """Test cleaning of photos directory."""
        # Create some dummy files
        mock_photoprism_api.photos_dir = temp_shared_dir
        (temp_shared_dir / "test1.jpg").touch()
        (temp_shared_dir / "test2.jpg").touch()

        mock_photoprism_api.clean_photos_directory()

        # Check that directory is empty
        assert len(list(temp_shared_dir.iterdir())) == 0


class TestAlbumSelection:
    """Test suite for album selection logic."""

    @patch("downloader.main.PhotoPrismAPI.process_whitelist")
    @patch("downloader.config.NUM_RANDOM_ALBUMS", 5)
    def test_select_all_when_not_enough_albums(self, mock_process_whitelist, mock_photoprism_api):
        """Test that all albums are selected when fewer than requested."""
        # Only 3 albums available
        mock_df = pd.DataFrame({"album_title": ["Album1", "Album2", "Album3"], "uid": ["uid1", "uid2", "uid3"]})
        mock_process_whitelist.return_value = mock_df

        result = mock_photoprism_api.get_random_albums()

        # Should return all 3 albums since we requested 5 but only 3 exist
        assert len(result) == 3

    @patch("downloader.main.PhotoPrismAPI.process_whitelist")
    def test_filter_missing_albums(self, mock_process_whitelist, mock_photoprism_api):
        """Test that albums without UIDs are filtered out."""
        # Some albums don't have UIDs (not found in PhotoPrism)
        mock_df = pd.DataFrame({"album_title": ["Album1", "Album2", "Missing"], "uid": ["uid1", "uid2", None]})
        mock_process_whitelist.return_value = mock_df

        result = mock_photoprism_api.get_random_albums()

        # Should only include albums with UIDs
        assert result is not None
        assert result["uid"].notna().all()
