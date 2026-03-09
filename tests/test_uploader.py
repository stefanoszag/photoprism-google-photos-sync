"""Tests for the Google Photos uploader module."""

import pytest

# Skip all tests in this module if Google API dependencies are not installed
pytest.importorskip("googleapiclient")
pytest.importorskip("google_auth_oauthlib")

from pathlib import Path  # noqa: E402
from unittest.mock import Mock, mock_open, patch  # noqa: E402


class TestGooglePhotosUploader:
    """Test suite for Google Photos uploader."""

    @patch("uploader.main.get_credentials")
    @patch("uploader.main.build")
    def test_get_or_create_album_existing(
        self, mock_build, mock_get_creds, mock_google_credentials, mock_google_photos_service
    ):
        """Test finding an existing album."""
        from uploader.main import get_or_create_album

        mock_get_creds.return_value = mock_google_credentials
        mock_build.return_value = mock_google_photos_service

        album_id = get_or_create_album(mock_google_photos_service, "Photoprism")

        assert album_id == "album_id_1"

    @patch("uploader.main.get_credentials")
    @patch("uploader.main.build")
    def test_get_or_create_album_new(
        self, mock_build, mock_get_creds, mock_google_credentials, mock_google_photos_service
    ):
        """Test creating a new album."""
        from uploader.main import get_or_create_album

        # Mock no existing albums
        mock_google_photos_service.albums().list().execute.return_value = {}

        album_id = get_or_create_album(mock_google_photos_service, "NewAlbum")

        assert album_id == "new_album_id"

    def test_get_media_type(self):
        """Test media type detection."""
        from uploader.main import get_media_type

        assert get_media_type("photo.jpg") == "image/jpeg"
        assert get_media_type("photo.png") == "image/png"
        assert get_media_type("photo.gif") == "image/gif"
        assert get_media_type("document.pdf") is None

    def test_upload_photo_skips_non_image(self, mock_google_credentials, mock_google_photos_service):
        """Test upload_photo returns False for non-image file (covers mime_type warning branch)."""
        from uploader.main import upload_photo

        result = upload_photo(mock_google_photos_service, mock_google_credentials, "document.pdf", "album_id_1")
        assert result is False

    @patch("requests.post")
    def test_upload_photo_upload_bytes_fails_non_200(
        self, mock_post, mock_google_credentials, mock_google_photos_service
    ):
        """Test upload_photo when upload bytes returns non-200 (covers logger.error and return False)."""
        from uploader.main import upload_photo

        mock_post.return_value.status_code = 500
        mock_post.return_value.content = b"error"

        result = upload_photo(mock_google_photos_service, mock_google_credentials, "test.jpg", "album_id_1")
        assert result is False

    @patch("requests.post")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_upload_photo_batch_create_fails_status(
        self, mock_file, mock_post, mock_google_credentials, mock_google_photos_service
    ):
        """Test upload_photo when batchCreate returns status message != Success."""
        from uploader.main import upload_photo

        mock_post.return_value.status_code = 200
        mock_post.return_value.content = b"upload_token_123"
        mock_google_photos_service.mediaItems().batchCreate().execute.return_value = {
            "newMediaItemResults": [{"status": {"message": "Invalid"}, "mediaItem": {"id": "x"}}]
        }

        result = upload_photo(mock_google_photos_service, mock_google_credentials, "test.jpg", "album_id_1")
        assert result is False

    @patch("requests.post")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_upload_photo_batch_create_no_results(
        self, mock_file, mock_post, mock_google_credentials, mock_google_photos_service
    ):
        """Test upload_photo when batchCreate returns no newMediaItemResults."""
        from uploader.main import upload_photo

        mock_post.return_value.status_code = 200
        mock_post.return_value.content = b"upload_token_123"
        mock_google_photos_service.mediaItems().batchCreate().execute.return_value = {}

        result = upload_photo(mock_google_photos_service, mock_google_credentials, "test.jpg", "album_id_1")
        assert result is False

    def test_list_photos(self, temp_shared_dir):
        """Test listing photos in a directory."""
        from uploader.main import list_photos

        # Create some test files
        (temp_shared_dir / "photo1.jpg").touch()
        (temp_shared_dir / "photo2.png").touch()
        (temp_shared_dir / "document.txt").touch()

        photos = list_photos(str(temp_shared_dir))

        # Should only include image files
        assert len(photos) == 2
        assert all(Path(p).suffix in [".jpg", ".png"] for p in photos)

    @patch("requests.post")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_upload_photo_success(self, mock_file, mock_post, mock_google_credentials, mock_google_photos_service):
        """Test successful photo upload."""
        from uploader.main import upload_photo

        # Mock successful upload token response
        mock_post.return_value.status_code = 200
        mock_post.return_value.content = b"upload_token_123"

        # Mock successful media item creation
        mock_google_photos_service.mediaItems().batchCreate().execute.return_value = {
            "newMediaItemResults": [{"status": {"message": "Success"}, "mediaItem": {"id": "media_id_1"}}]
        }

        result = upload_photo(mock_google_photos_service, mock_google_credentials, "test.jpg", "album_id_1")

        assert result is True

    @patch("requests.post")
    def test_upload_photo_failure(self, mock_post, mock_google_credentials, mock_google_photos_service):
        """Test failed photo upload."""
        from uploader.main import upload_photo

        # Mock failed upload
        mock_post.return_value.status_code = 500

        result = upload_photo(mock_google_photos_service, mock_google_credentials, "test.jpg", "album_id_1")

        assert result is False

    def test_cleanup_album(self, mock_google_credentials, mock_google_photos_service):
        """Test album cleanup."""
        from uploader.main import cleanup_album

        # Mock existing media items
        mock_google_photos_service.mediaItems().search().execute.return_value = {
            "mediaItems": [{"id": "media1"}, {"id": "media2"}]
        }

        result = cleanup_album(mock_google_photos_service, mock_google_credentials, "album_id_1")

        assert result is True

    def test_cleanup_album_no_media_items(self, mock_google_credentials, mock_google_photos_service):
        """Test cleanup_album when album has no photos (covers early return)."""
        from uploader.main import cleanup_album

        mock_google_photos_service.mediaItems().search().execute.return_value = {}
        result = cleanup_album(mock_google_photos_service, mock_google_credentials, "album_id_1")
        assert result is True

    def test_cleanup_album_exception(self, mock_google_credentials, mock_google_photos_service):
        """Test cleanup_album when API raises (covers except branch)."""
        from uploader.main import cleanup_album

        mock_google_photos_service.mediaItems().search().execute.side_effect = Exception("API error")
        result = cleanup_album(mock_google_photos_service, mock_google_credentials, "album_id_1")
        assert result is False

    def test_cleanup_shared_folder(self, temp_shared_dir):
        """Test shared folder cleanup."""
        from uploader.main import cleanup_shared_folder

        # Create test files
        file1 = temp_shared_dir / "photo1.jpg"
        file2 = temp_shared_dir / "photo2.jpg"
        file1.touch()
        file2.touch()

        photos = [str(file1), str(file2)]
        result = cleanup_shared_folder(photos)

        assert result is True
        assert not file1.exists()
        assert not file2.exists()

    def test_cleanup_shared_folder_delete_fails(self, temp_shared_dir):
        """Test cleanup_shared_folder when os.remove raises (covers inner except)."""
        from uploader.main import cleanup_shared_folder

        file1 = temp_shared_dir / "photo1.jpg"
        file1.touch()
        with patch("os.remove", side_effect=OSError("Permission denied")):
            result = cleanup_shared_folder([str(file1)])
        assert result is False

    def test_cleanup_shared_folder_outer_exception(self):
        """Test cleanup_shared_folder when iteration raises (covers outer except)."""
        from uploader.main import cleanup_shared_folder

        with patch("uploader.main.logger"):
            result = cleanup_shared_folder(None)  # type: ignore[arg-type]
        assert result is False

    @patch("uploader.main.build")
    def test_get_storage_quota(self, mock_build, mock_google_credentials):
        """Test storage quota retrieval."""
        from uploader.main import get_storage_quota

        # Mock Drive API service
        mock_drive_service = Mock()
        mock_drive_service.about().get().execute.return_value = {
            "storageQuota": {
                "usage": "10737418240",  # 10 GB in bytes
                "limit": "107374182400",  # 100 GB in bytes
            }
        }
        mock_build.return_value = mock_drive_service

        quota = get_storage_quota(mock_google_credentials)

        assert quota is not None
        assert quota["usage_gb"] == 10.0
        assert quota["limit_gb"] == 100.0

    @patch("uploader.main.build")
    def test_get_storage_quota_exception(self, mock_build, mock_google_credentials):
        """Test get_storage_quota when API raises (covers except return None)."""
        from uploader.main import get_storage_quota

        mock_build.return_value.about.return_value.get.return_value.execute.side_effect = Exception("API error")
        quota = get_storage_quota(mock_google_credentials)
        assert quota is None

    @patch("requests.post")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_upload_photo_exception_during_upload(
        self, mock_file, mock_post, mock_google_credentials, mock_google_photos_service
    ):
        """Test upload_photo when an exception is raised (covers general except)."""
        from uploader.main import upload_photo

        mock_post.side_effect = Exception("Network error")
        result = upload_photo(mock_google_photos_service, mock_google_credentials, "test.jpg", "album_id_1")
        assert result is False


class TestUploadToAlbum:
    """Test upload_to_album orchestration."""

    @patch("uploader.main.alert_manager")
    @patch("uploader.main.cleanup_shared_folder")
    @patch("uploader.main.upload_photo")
    @patch("uploader.main.list_photos")
    @patch("uploader.main.cleanup_album")
    @patch("uploader.main.get_or_create_album")
    @patch("uploader.main.get_storage_quota")
    @patch("uploader.main.get_credentials")
    @patch("uploader.main.build")
    def test_upload_to_album_success_path(
        self,
        mock_build,
        mock_get_creds,
        mock_quota,
        mock_get_album,
        mock_cleanup_album,
        mock_list_photos,
        mock_upload,
        mock_cleanup_folder,
        mock_alert,
        mock_google_credentials,
        mock_google_photos_service,
        temp_shared_dir,
    ):
        """Test upload_to_album happy path: credentials, quota, album, cleanup, upload, summary."""
        from uploader.main import upload_to_album

        (temp_shared_dir / "a.jpg").touch()
        mock_get_creds.return_value = mock_google_credentials
        mock_quota.return_value = {
            "usage_gb": 5.0,
            "limit_gb": 100.0,
            "usage_bytes": 5 * 2**30,
            "limit_bytes": 100 * 2**30,
        }
        mock_build.return_value = mock_google_photos_service
        mock_get_album.return_value = "album_1"
        mock_cleanup_album.return_value = True
        mock_list_photos.return_value = [str(temp_shared_dir / "a.jpg")]
        mock_upload.return_value = True
        mock_cleanup_folder.return_value = True

        with patch("uploader.main.SHARED_FOLDER", str(temp_shared_dir)):
            upload_to_album()

        mock_cleanup_album.assert_called_once()
        assert mock_upload.call_count == 1
        mock_cleanup_folder.assert_called_once()
        mock_alert.send_alert.assert_called()

    @patch("uploader.main.get_credentials")
    def test_upload_to_album_exception_sends_alert(self, mock_get_creds):
        """Test upload_to_album when get_credentials raises (covers except and finally summary)."""
        from uploader.main import upload_to_album

        mock_get_creds.side_effect = Exception("Auth failed")
        with patch("uploader.main.alert_manager") as mock_alert:
            upload_to_album()
        mock_alert.send_alert.assert_called()
        # Finally block always sends summary
        assert mock_alert.send_alert.call_count >= 1


class TestAuthentication:
    """Test suite for OAuth2 authentication."""

    @patch("uploader.auth.Credentials.from_authorized_user_file")
    @patch("uploader.auth.os.path.exists")
    def test_get_credentials_with_valid_token(self, mock_exists, mock_from_file):
        """Test getting credentials with valid token."""
        from uploader.auth import get_credentials

        mock_exists.return_value = True
        mock_creds = Mock()
        mock_creds.valid = True
        mock_from_file.return_value = mock_creds

        creds = get_credentials()

        assert creds is not None
        assert creds.valid is True

    @patch("uploader.auth.Credentials.from_authorized_user_file")
    @patch("uploader.auth.os.path.exists")
    def test_get_credentials_load_token_exception_then_missing_credentials_file(self, mock_exists, mock_from_file):
        """Test token file exists but loading raises; then missing credentials file raises FileNotFoundError."""
        from uploader.auth import get_credentials

        mock_from_file.side_effect = Exception("Corrupt token")
        # First call: TOKEN_FILE exists; second call: CREDENTIALS_FILE does not exist
        mock_exists.side_effect = [True, False]

        with pytest.raises(FileNotFoundError, match="Missing credentials file"):
            get_credentials()

    @patch("uploader.auth.open", new_callable=mock_open)
    @patch("uploader.auth.Request")
    @patch("uploader.auth.Credentials.from_authorized_user_file")
    @patch("uploader.auth.os.path.exists")
    def test_get_credentials_expired_refresh_success(self, mock_exists, mock_from_file, mock_request, mock_open_func):
        """Test expired token is refreshed and saved."""
        from uploader.auth import get_credentials

        mock_exists.return_value = True
        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds.refresh = Mock()
        mock_creds.to_json = Mock(return_value="{}")
        mock_from_file.return_value = mock_creds

        creds = get_credentials()

        assert creds is mock_creds
        mock_creds.refresh.assert_called_once()
        mock_open_func().write.assert_called()

    @patch("uploader.auth.Credentials.from_authorized_user_file")
    @patch("uploader.auth.os.path.exists")
    def test_get_credentials_expired_refresh_fails_then_missing_credentials_file(self, mock_exists, mock_from_file):
        """Test expired token refresh fails; then missing credentials file raises FileNotFoundError."""
        from uploader.auth import get_credentials

        mock_exists.side_effect = [True, False]
        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds.refresh = Mock(side_effect=Exception("Refresh failed"))
        mock_from_file.return_value = mock_creds

        with pytest.raises(FileNotFoundError, match="Missing credentials file"):
            get_credentials()

    @patch("uploader.auth.InstalledAppFlow")
    @patch("uploader.auth.open", new_callable=mock_open)
    @patch("uploader.auth.os.path.exists")
    def test_get_credentials_no_token_oauth_flow(self, mock_exists, mock_open_func, mock_flow):
        """Test OAuth flow when no token file; credentials file exists and flow is run."""
        from uploader.auth import get_credentials

        mock_exists.side_effect = [False, True]  # no token file, credentials file exists
        mock_creds = Mock()
        mock_creds.valid = True
        mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = mock_creds
        mock_creds.to_json = Mock(return_value="{}")

        creds = get_credentials()

        assert creds is mock_creds
        mock_flow.from_client_secrets_file.return_value.run_local_server.assert_called_once_with(port=0)
        mock_open_func().write.assert_called()


class TestTokenManager:
    """Test suite for token manager utilities."""

    @patch("uploader.token_manager.open", new_callable=mock_open)
    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_refresh_token_success(self, mock_exists, mock_from_file, mock_open_func):
        """Test successful token refresh."""
        from uploader.token_manager import refresh_token

        mock_exists.return_value = True
        mock_creds = Mock()
        mock_creds.refresh_token = "refresh_token"
        mock_creds.to_json = Mock(return_value="{}")
        mock_from_file.return_value = mock_creds

        with patch("uploader.token_manager.Request"):
            result = refresh_token()

        assert result is True
        mock_creds.refresh.assert_called_once()

    @patch("uploader.token_manager.os.path.exists")
    def test_refresh_token_failure_no_file(self, mock_exists):
        """Test refresh when token file does not exist (raises TokenRefreshError)."""
        from uploader.token_manager import TokenRefreshError, refresh_token

        mock_exists.return_value = False

        with pytest.raises(TokenRefreshError, match="Token file not found"):
            refresh_token()

    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_refresh_token_no_refresh_token_in_file(self, mock_exists, mock_from_file):
        """Test refresh when credentials have no refresh_token (raises TokenRefreshError)."""
        from uploader.token_manager import TokenRefreshError, refresh_token

        mock_exists.return_value = True
        mock_creds = Mock()
        mock_creds.refresh_token = None
        mock_from_file.return_value = mock_creds

        with pytest.raises(TokenRefreshError, match="No refresh token available"):
            refresh_token()

    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_refresh_token_failure_exception(self, mock_exists, mock_from_file):
        """Test refresh when an exception is raised."""
        from uploader.token_manager import refresh_token

        mock_exists.return_value = True
        mock_from_file.side_effect = Exception("Refresh failed")

        result = refresh_token()

        assert result is False

    @patch("uploader.token_manager.os.path.exists")
    def test_check_token_status_no_file(self, mock_exists):
        """Test check_token_status when token file does not exist."""
        from uploader.token_manager import check_token_status

        mock_exists.return_value = False
        assert check_token_status() is False

    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_check_token_status_success_valid(self, mock_exists, mock_from_file):
        """Test check_token_status with valid token (no expiry)."""
        from uploader.token_manager import check_token_status

        mock_exists.return_value = True
        mock_creds = Mock()
        mock_creds.refresh_token = "rt"
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds.expiry = None
        mock_from_file.return_value = mock_creds

        assert check_token_status() is True

    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_check_token_status_future_expiry(self, mock_exists, mock_from_file):
        """Test check_token_status with future expiry (covers 'Expires in' branch)."""
        from datetime import datetime, timedelta, timezone

        from uploader.token_manager import check_token_status

        mock_exists.return_value = True
        mock_creds = Mock()
        mock_creds.refresh_token = "rt"
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_from_file.return_value = mock_creds

        assert check_token_status() is True

    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_check_token_status_expired_with_refresh(self, mock_exists, mock_from_file):
        """Test check_token_status when expired but refresh token available (45-46)."""
        from datetime import datetime, timedelta, timezone

        from uploader.token_manager import check_token_status

        mock_exists.return_value = True
        mock_creds = Mock()
        mock_creds.refresh_token = "rt"
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_from_file.return_value = mock_creds

        assert check_token_status() is True

    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_check_token_status_expired_no_refresh(self, mock_exists, mock_from_file):
        """Test check_token_status when expired and no refresh token (47-48)."""
        from uploader.token_manager import check_token_status

        mock_exists.return_value = True
        mock_creds = Mock()
        mock_creds.refresh_token = None
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.expiry = None  # skip expiry time block
        mock_from_file.return_value = mock_creds

        assert check_token_status() is True

    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.os.path.exists")
    def test_check_token_status_exception(self, mock_exists, mock_from_file):
        """Test check_token_status when reading token raises."""
        from uploader.token_manager import check_token_status

        mock_exists.return_value = True
        mock_from_file.side_effect = Exception("Corrupt file")
        assert check_token_status() is False

    @patch("uploader.token_manager.os.path.exists")
    def test_generate_new_token_no_credentials_file(self, mock_exists):
        """Test generate_new_token when credentials file missing (87-90)."""
        from uploader.token_manager import generate_new_token

        mock_exists.return_value = False
        assert generate_new_token() is False

    @patch("uploader.token_manager.open", new_callable=mock_open)
    @patch("uploader.token_manager.InstalledAppFlow")
    @patch("uploader.token_manager.os.path.exists")
    def test_generate_new_token_success(self, mock_exists, mock_flow, mock_open_func):
        """Test generate_new_token success path."""
        from uploader.token_manager import generate_new_token

        mock_exists.return_value = True
        mock_creds = Mock()
        mock_creds.to_json = Mock(return_value="{}")
        mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = mock_creds

        assert generate_new_token() is True
        mock_open_func().write.assert_called()

    @patch("uploader.token_manager.InstalledAppFlow")
    @patch("uploader.token_manager.os.path.exists")
    def test_generate_new_token_exception(self, mock_exists, mock_flow):
        """Test generate_new_token when flow raises (106-108)."""
        from uploader.token_manager import generate_new_token

        mock_exists.return_value = True
        mock_flow.from_client_secrets_file.return_value.run_local_server.side_effect = Exception("OAuth failed")
        assert generate_new_token() is False

    @patch("uploader.token_manager.check_token_status")
    def test_validate_token_for_remote_check_fails(self, mock_check):
        """Test validate_token_for_remote when check_token_status returns False."""
        from uploader.token_manager import validate_token_for_remote

        mock_check.return_value = False
        assert validate_token_for_remote() is False

    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.check_token_status")
    def test_validate_token_for_remote_no_refresh_token(self, mock_check, mock_from_file):
        """Test validate_token_for_remote when token has no refresh_token (119-122)."""
        from uploader.token_manager import validate_token_for_remote

        mock_check.return_value = True
        mock_creds = Mock()
        mock_creds.refresh_token = None
        mock_from_file.return_value = mock_creds
        assert validate_token_for_remote() is False

    @patch("uploader.token_manager.refresh_token")
    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.check_token_status")
    def test_validate_token_for_remote_expired_refresh_ok(self, mock_check, mock_from_file, mock_refresh):
        """Test validate when expired but refresh succeeds (124-128)."""
        from uploader.token_manager import validate_token_for_remote

        mock_check.return_value = True
        mock_creds = Mock()
        mock_creds.refresh_token = "rt"
        mock_creds.expired = True
        mock_from_file.return_value = mock_creds
        mock_refresh.return_value = True
        assert validate_token_for_remote() is True

    @patch("uploader.token_manager.refresh_token")
    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.check_token_status")
    def test_validate_token_for_remote_expired_refresh_fails(self, mock_check, mock_from_file, mock_refresh):
        """Test validate when expired and refresh fails (129-131)."""
        from uploader.token_manager import validate_token_for_remote

        mock_check.return_value = True
        mock_creds = Mock()
        mock_creds.refresh_token = "rt"
        mock_creds.expired = True
        mock_from_file.return_value = mock_creds
        mock_refresh.return_value = False
        assert validate_token_for_remote() is False

    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.check_token_status")
    def test_validate_token_for_remote_valid(self, mock_check, mock_from_file):
        """Test validate when token is valid (132-134)."""
        from uploader.token_manager import validate_token_for_remote

        mock_check.return_value = True
        mock_creds = Mock()
        mock_creds.refresh_token = "rt"
        mock_creds.expired = False
        mock_from_file.return_value = mock_creds
        assert validate_token_for_remote() is True

    @patch("uploader.token_manager.Credentials.from_authorized_user_file")
    @patch("uploader.token_manager.check_token_status")
    def test_validate_token_for_remote_exception(self, mock_check, mock_from_file):
        """Test validate when reading token raises (136-138)."""
        from uploader.token_manager import validate_token_for_remote

        mock_check.return_value = True
        mock_from_file.side_effect = Exception("Read error")
        assert validate_token_for_remote() is False

    @patch("uploader.token_manager.logger")
    def test_main_no_args_prints_usage(self, mock_logger):
        """Test main() with no command (covers 144-150 usage and return)."""
        from uploader.token_manager import main

        with patch("uploader.token_manager.sys.argv", [""]):
            main()
        assert mock_logger.info.call_count >= 4  # Usage + Commands lines

    @patch("uploader.token_manager.logger")
    @patch("uploader.token_manager.check_token_status")
    def test_main_status_command(self, mock_check, mock_logger):
        """Test main() with 'status' command."""
        from uploader.token_manager import main

        with patch("uploader.token_manager.sys.argv", ["", "status"]):
            main()
        mock_check.assert_called_once()

    @patch("uploader.token_manager.refresh_token")
    def test_main_refresh_command(self, mock_refresh):
        """Test main() with 'refresh' command."""
        from uploader.token_manager import main

        with patch("uploader.token_manager.sys.argv", ["", "refresh"]):
            main()
        mock_refresh.assert_called_once()

    @patch("uploader.token_manager.generate_new_token")
    def test_main_generate_command(self, mock_generate):
        """Test main() with 'generate' command."""
        from uploader.token_manager import main

        with patch("uploader.token_manager.sys.argv", ["", "generate"]):
            main()
        mock_generate.assert_called_once()

    @patch("uploader.token_manager.validate_token_for_remote")
    def test_main_validate_command(self, mock_validate):
        """Test main() with 'validate' command."""
        from uploader.token_manager import main

        with patch("uploader.token_manager.sys.argv", ["", "validate"]):
            main()
        mock_validate.assert_called_once()

    @patch("uploader.token_manager.logger")
    def test_main_unknown_command(self, mock_logger):
        """Test main() with unknown command (162-163)."""
        from uploader.token_manager import main

        with patch("uploader.token_manager.sys.argv", ["", "unknown"]):
            main()
        mock_logger.error.assert_called()
