"""Tests for the token manager (TokenRefreshError, refresh_token, permanent failure detection)."""

import pytest

pytest.importorskip("google.auth")
pytest.importorskip("google.oauth2")

from unittest.mock import MagicMock, mock_open, patch  # noqa: E402

from google.auth.exceptions import RefreshError  # noqa: E402

from uploader.token_manager import (  # noqa: E402
    TokenRefreshError,
    _is_permanent_refresh_failure,
    refresh_token,
)


class TestTokenRefreshError:
    """Tests for TokenRefreshError exception."""

    def test_token_refresh_error_is_exception(self):
        """TokenRefreshError is a subclass of Exception."""
        assert issubclass(TokenRefreshError, Exception)

    def test_token_refresh_error_can_be_raised_with_message(self):
        """TokenRefreshError can be raised and carries a message."""
        with pytest.raises(TokenRefreshError, match="manual re-auth"):
            raise TokenRefreshError("manual re-auth required")


class TestIsPermanentRefreshFailure:
    """Tests for _is_permanent_refresh_failure helper."""

    def test_invalid_grant_returns_true(self):
        """invalid_grant in error message is treated as permanent."""
        assert _is_permanent_refresh_failure(Exception("invalid_grant: Bad request")) is True
        assert _is_permanent_refresh_failure(RefreshError("invalid_grant")) is True

    def test_token_expired_or_revoked_returns_true(self):
        """'Token has been expired or revoked' is treated as permanent."""
        assert _is_permanent_refresh_failure(Exception("Token has been expired or revoked.")) is True

    def test_revoked_and_token_returns_true(self):
        """'revoked' and 'token' in message is treated as permanent."""
        assert _is_permanent_refresh_failure(Exception("Token was revoked by user")) is True

    def test_transient_errors_return_false(self):
        """Network and other transient errors are not permanent."""
        assert _is_permanent_refresh_failure(Exception("Connection timeout")) is False
        assert _is_permanent_refresh_failure(Exception("Temporary failure")) is False
        assert _is_permanent_refresh_failure(RefreshError("Network unreachable")) is False

    def test_revoked_and_token_both_required(self):
        """Both 'revoked' and 'token' must be in message to be treated as permanent."""
        assert _is_permanent_refresh_failure(Exception("Token was revoked by user")) is True
        assert _is_permanent_refresh_failure(Exception("Access revoked")) is False  # no "token"
        assert _is_permanent_refresh_failure(Exception("Something revoked elsewhere")) is False  # no "token"


class TestRefreshToken:
    """Tests for refresh_token function."""

    @patch("uploader.token_manager.os.path.exists")
    def test_raises_when_token_file_missing(self, mock_exists):
        """refresh_token raises TokenRefreshError when token file does not exist."""
        mock_exists.return_value = False
        with pytest.raises(TokenRefreshError, match="Token file not found"):
            refresh_token()

    @patch("uploader.token_manager.open", new_callable=mock_open, read_data='{"refresh_token": null}')
    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_raises_when_no_refresh_token_in_creds(self, mock_exists, mock_from_file, mock_file):
        """refresh_token raises TokenRefreshError when credentials have no refresh_token."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.refresh_token = None
        mock_from_file.return_value = mock_creds
        with pytest.raises(TokenRefreshError, match="No refresh token available"):
            refresh_token()

    @patch("uploader.token_manager.open", new_callable=mock_open, read_data='{"refresh_token": "rt123"}')
    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_raises_on_refresh_error_invalid_grant(self, mock_exists, mock_from_file, mock_file):
        """refresh_token raises TokenRefreshError when RefreshError has invalid_grant."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.refresh_token = "rt123"
        mock_creds.refresh.side_effect = RefreshError("invalid_grant: Token has been expired or revoked.")
        mock_from_file.return_value = mock_creds
        with pytest.raises(TokenRefreshError, match="invalid_grant"):
            refresh_token()

    @patch("uploader.token_manager.open", new_callable=mock_open, read_data='{"refresh_token": "rt123"}')
    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_raises_on_generic_exception_with_permanent_message(self, mock_exists, mock_from_file, mock_file):
        """refresh_token raises TokenRefreshError when a non-RefreshError has permanent-failure message (covers except Exception branch)."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.refresh_token = "rt123"
        mock_creds.refresh.side_effect = Exception("invalid_grant: Token has been expired or revoked.")
        mock_from_file.return_value = mock_creds
        with pytest.raises(TokenRefreshError, match="invalid_grant"):
            refresh_token()

    @patch("uploader.token_manager.open", new_callable=mock_open, read_data='{"refresh_token": "rt123"}')
    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_returns_false_on_transient_refresh_error(self, mock_exists, mock_from_file, mock_file):
        """refresh_token returns False on transient RefreshError (e.g. network)."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.refresh_token = "rt123"
        mock_creds.refresh.side_effect = RefreshError("Connection timed out")
        mock_from_file.return_value = mock_creds
        assert refresh_token() is False

    @patch("uploader.token_manager.open", new_callable=mock_open, read_data='{"refresh_token": "rt123"}')
    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_returns_true_and_writes_when_refresh_succeeds(self, mock_exists, mock_from_file, mock_file):
        """refresh_token returns True and writes token file when refresh succeeds."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.refresh_token = "rt123"
        mock_creds.to_json.return_value = '{"access_token":"new"}'
        mock_from_file.return_value = mock_creds
        result = refresh_token()
        assert result is True
        mock_creds.refresh.assert_called_once()
        mock_file().write.assert_called()
        mock_file().write.assert_called_with('{"access_token":"new"}')
