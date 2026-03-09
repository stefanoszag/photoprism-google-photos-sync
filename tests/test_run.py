"""Tests for run.py scheduler and token-refresh failure handling."""

import sys
from unittest.mock import MagicMock, patch

import schedule

# Stub heavy deps so "import run" does not load downloader (pandas/numpy) or resizer
_orig_config = sys.modules.get("config")
_orig_downloader = sys.modules.get("downloader")
_orig_resizer = sys.modules.get("resizer")
_config = MagicMock()
_config.SCHEDULER_INTERVAL_SECONDS = 86400
_config.TOKEN_REFRESH_ΙNTERVAL_MINUTES = 50
sys.modules["config"] = _config
sys.modules["downloader"] = MagicMock()
sys.modules["resizer"] = MagicMock()

import run  # noqa: E402

# Restore so other test modules get real config/downloader/resizer when they import
if _orig_config is not None:
    sys.modules["config"] = _orig_config
elif "config" in sys.modules:
    del sys.modules["config"]
if _orig_downloader is not None:
    sys.modules["downloader"] = _orig_downloader
elif "downloader" in sys.modules:
    del sys.modules["downloader"]
if _orig_resizer is not None:
    sys.modules["resizer"] = _orig_resizer
elif "resizer" in sys.modules:
    del sys.modules["resizer"]

from uploader.token_manager import TokenRefreshError  # noqa: E402


class TestShutdownScheduler:
    """Tests for shutdown_scheduler."""

    def test_clears_schedule_and_sets_flag(self):
        """shutdown_scheduler clears all jobs and sets scheduler_should_stop."""
        # Add a dummy job so we can assert clear was called
        run.scheduler_should_stop = False
        schedule.every(10).minutes.do(lambda: None)
        assert len(schedule.get_jobs()) >= 1

        run.shutdown_scheduler()

        assert run.scheduler_should_stop is True
        assert len(schedule.get_jobs()) == 0

    def test_idempotent_after_clear(self):
        """Calling shutdown_scheduler again is safe (schedule already clear)."""
        run.scheduler_should_stop = True
        run.shutdown_scheduler()
        assert run.scheduler_should_stop is True
        assert len(schedule.get_jobs()) == 0


class TestScheduledTokenRefresh:
    """Tests for scheduled_token_refresh on TokenRefreshError."""

    @patch("run.sys.exit")
    @patch("run.shutdown_scheduler")
    @patch("run.alert_manager")
    @patch("run.refresh_google_token")
    def test_on_token_refresh_error_sends_alert_and_shuts_down(
        self, mock_refresh, mock_alert_manager, mock_shutdown, mock_exit
    ):
        """When refresh raises TokenRefreshError, alert is sent and scheduler shuts down."""
        mock_refresh.side_effect = TokenRefreshError("invalid_grant: Token expired")

        run.scheduled_token_refresh()

        mock_alert_manager.send_alert.assert_called_once()
        call_kwargs = mock_alert_manager.send_alert.call_args[1]
        assert call_kwargs["subject"] == "Token Refresh Failed - Manual Action Required"
        assert "manual re-auth" in call_kwargs["message"].lower() or "token" in call_kwargs["message"].lower()
        assert "python -m uploader.token_manager generate" in call_kwargs["message"]
        assert call_kwargs["methods"] == ["telegram"]
        mock_shutdown.assert_called_once()
        mock_exit.assert_called_once_with(1)

    @patch("run.refresh_google_token")
    def test_on_success_no_alert_no_shutdown(self, mock_refresh):
        """When refresh succeeds, no alert and no shutdown."""
        mock_refresh.return_value = True
        with patch("run.alert_manager") as mock_alert:
            with patch("run.shutdown_scheduler") as mock_shutdown:
                with patch("run.sys.exit") as mock_exit:
                    run.scheduled_token_refresh()
        mock_alert.send_alert.assert_not_called()
        mock_shutdown.assert_not_called()
        mock_exit.assert_not_called()

    @patch("run.refresh_google_token")
    def test_on_generic_exception_no_alert_no_shutdown(self, mock_refresh):
        """When refresh raises a non-TokenRefreshError, no alert and no shutdown."""
        mock_refresh.side_effect = RuntimeError("Network error")
        with patch("run.alert_manager") as mock_alert:
            with patch("run.shutdown_scheduler") as mock_shutdown:
                with patch("run.sys.exit") as mock_exit:
                    run.scheduled_token_refresh()
        mock_alert.send_alert.assert_not_called()
        mock_shutdown.assert_not_called()
        mock_exit.assert_not_called()
