"""Tests for the alert system."""

from unittest.mock import MagicMock, Mock, patch

import pytest


class TestAlertManager:
    """Test suite for alert manager."""

    @pytest.fixture
    def alert_manager(self):
        """Create an AlertManager instance."""
        from utils.alerts import AlertManager

        return AlertManager()

    def test_initialization(self, alert_manager):
        """Test AlertManager initialization."""
        assert alert_manager is not None
        assert hasattr(alert_manager, "smtp_host")
        assert hasattr(alert_manager, "slack_webhook_url")
        assert hasattr(alert_manager, "telegram_bot_token")

    @patch.dict(
        "os.environ",
        {
            "SMTP_HOST": "smtp.test.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "test@test.com",
            "SMTP_PASSWORD": "password",
            "ALERT_EMAIL": "alert@test.com",
        },
    )
    @patch("smtplib.SMTP")
    def test_send_email_alert_success(self, mock_smtp):
        """Test successful email alert."""
        from utils.alerts import AlertManager

        manager = AlertManager()
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = manager.send_email_alert("Test Subject", "Test Message")

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@test.com", "password")
        mock_server.send_message.assert_called_once()

    @patch.dict(
        "os.environ",
        {"SMTP_USER": "", "SMTP_PASSWORD": "", "ALERT_EMAIL": ""},
        clear=False,
    )
    def test_send_email_alert_not_configured(self):
        """Test email alert when not configured (isolated from real env)."""
        from utils.alerts import AlertManager

        manager = AlertManager()
        result = manager.send_email_alert("Test", "Message")

        assert result is False

    @patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"})
    @patch("utils.alerts.requests.post")
    def test_send_slack_alert_success(self, mock_post):
        """Test successful Slack alert."""
        from utils.alerts import AlertManager

        manager = AlertManager()
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()

        result = manager.send_slack_alert("Test Message")

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert "json" in call_kwargs
        assert "Test Message" in call_kwargs["json"]["text"]

    @patch.dict("os.environ", {"SLACK_WEBHOOK_URL": ""}, clear=False)
    def test_send_slack_alert_not_configured(self):
        """Test Slack alert when not configured (isolated from real env)."""
        from utils.alerts import AlertManager

        manager = AlertManager()
        result = manager.send_slack_alert("Test")

        assert result is False

    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test_token", "TELEGRAM_CHAT_ID": "123456"})
    @patch("utils.alerts.requests.post")
    def test_send_telegram_alert_success(self, mock_post):
        """Test successful Telegram alert."""
        from utils.alerts import AlertManager

        manager = AlertManager()
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()

        result = manager.send_telegram_alert("Test Message")

        assert result is True
        mock_post.assert_called_once()

    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""})
    def test_send_telegram_alert_not_configured(self):
        """Test Telegram alert when not configured (isolated from real env)."""
        from utils.alerts import AlertManager

        manager = AlertManager()
        result = manager.send_telegram_alert("Test")

        assert result is False

    @patch.dict(
        "os.environ",
        {
            "SMTP_HOST": "smtp.test.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "test@test.com",
            "SMTP_PASSWORD": "password",
            "ALERT_EMAIL": "alert@test.com",
        },
    )
    @patch("smtplib.SMTP")
    def test_send_alert_multiple_methods(self, mock_smtp):
        """Test sending alert through multiple methods."""
        from utils.alerts import AlertManager

        manager = AlertManager()
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # This should attempt email (others not configured)
        manager.send_alert("Test Subject", "Test Message", methods=["email"])

        mock_server.send_message.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_email_alert_failure(self, mock_smtp):
        """Test email alert failure."""
        from utils.alerts import AlertManager

        mock_smtp.side_effect = Exception("SMTP Error")

        with patch.dict(
            "os.environ", {"SMTP_USER": "test@test.com", "SMTP_PASSWORD": "password", "ALERT_EMAIL": "alert@test.com"}
        ):
            manager = AlertManager()
            result = manager.send_email_alert("Test", "Message")

            assert result is False

    @patch("utils.alerts.requests.post")
    def test_send_slack_alert_failure(self, mock_post):
        """Test Slack alert failure."""
        from utils.alerts import AlertManager

        mock_post.side_effect = Exception("Network Error")

        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
            manager = AlertManager()
            result = manager.send_slack_alert("Test")

            assert result is False

    @patch("utils.alerts.requests.post")
    def test_send_telegram_alert_failure(self, mock_post):
        """Test Telegram alert failure."""
        from utils.alerts import AlertManager

        mock_post.side_effect = Exception("API Error")

        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test_token", "TELEGRAM_CHAT_ID": "123456"}):
            manager = AlertManager()
            result = manager.send_telegram_alert("Test")

            assert result is False


class TestAlertIntegration:
    """Integration tests for alert system."""

    @patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"})
    @patch("utils.alerts.requests.post")
    def test_alert_on_high_storage(self, mock_post):
        """Test alert triggered on high storage usage."""
        from utils.alerts import AlertManager

        manager = AlertManager()
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()

        # Simulate high storage alert
        manager.send_alert(subject="High Storage Usage", message="Storage usage is at 96%", methods=["slack"])

        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        # Slack alert combines prefix + message (subject not in body)
        assert "Storage usage is at 96%" in call_kwargs["json"]["text"]
