"""Tests for the PhotoPrism downloader auth module (get_token)."""

from unittest.mock import Mock, patch

import pytest
import requests


class TestGetToken:
    """Tests for downloader.auth.get_token."""

    @patch("downloader.auth.config.PASSWORD", "pass")
    @patch("downloader.auth.config.USERNAME", "")
    def test_get_token_missing_username_raises(self):
        """Missing USERNAME raises Exception."""
        from downloader.auth import get_token

        with pytest.raises(Exception, match="PHOTOPRISM_USERNAME and PHOTOPRISM_PASSWORD must be set"):
            get_token("https://photoprism.example.com")

    @patch("downloader.auth.config.USERNAME", "user")
    @patch("downloader.auth.config.PASSWORD", "")
    def test_get_token_missing_password_raises(self):
        """Missing PASSWORD raises Exception."""
        from downloader.auth import get_token

        with pytest.raises(Exception, match="PHOTOPRISM_USERNAME and PHOTOPRISM_PASSWORD must be set"):
            get_token("https://photoprism.example.com")

    @patch("requests.post")
    @patch("downloader.auth.config.PASSWORD", "secret")
    @patch("downloader.auth.config.USERNAME", "admin")
    def test_get_token_success(self, mock_post):
        """Successful login returns access token."""
        from downloader.auth import get_token

        mock_post.return_value.json.return_value = {"access_token": "abc123"}
        mock_post.return_value.raise_for_status = Mock()

        token = get_token("https://photoprism.example.com")

        assert token == "abc123"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://photoprism.example.com/api/v1/session"
        assert call_args[1]["json"] == {"username": "admin", "password": "secret"}

    @patch("requests.post")
    @patch("downloader.auth.config.PASSWORD", "secret")
    @patch("downloader.auth.config.USERNAME", "admin")
    def test_get_token_no_token_in_response_raises(self, mock_post):
        """Response without access_token raises Exception."""
        from downloader.auth import get_token

        mock_post.return_value.json.return_value = {}
        mock_post.return_value.raise_for_status = Mock()

        with pytest.raises(Exception, match="Login failed, no token received"):
            get_token("https://photoprism.example.com")

    @patch("requests.post")
    @patch("downloader.auth.config.PASSWORD", "secret")
    @patch("downloader.auth.config.USERNAME", "admin")
    def test_get_token_request_exception_reraised(self, mock_post):
        """RequestException is re-raised."""
        from downloader.auth import get_token

        mock_post.side_effect = requests.exceptions.RequestException("Connection error")

        with pytest.raises(requests.exceptions.RequestException, match="Connection error"):
            get_token("https://photoprism.example.com")

    @patch("requests.post")
    @patch("downloader.auth.config.PASSWORD", "secret")
    @patch("downloader.auth.config.USERNAME", "admin")
    def test_get_token_http_error_reraised(self, mock_post):
        """HTTP error (raise_for_status) is re-raised."""
        from downloader.auth import get_token

        mock_post.return_value.json.return_value = {"error": "Unauthorized"}
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("401")

        with pytest.raises(requests.exceptions.HTTPError):
            get_token("https://photoprism.example.com")
