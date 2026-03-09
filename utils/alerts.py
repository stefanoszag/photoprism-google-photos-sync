"""Alerting module for the PhotoPrism Google Photos workflow."""

import logging
import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class AlertManager:
    def __init__(self):
        # Email configuration
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.alert_email = os.getenv("ALERT_EMAIL")

        # Slack configuration
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")

        # Telegram configuration
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def send_email_alert(self, subject: str, message: str) -> bool:
        """Send an email alert.

        Args:
            subject: Email subject
            message: Email body

        Returns:
            bool: True if email was sent successfully
        """
        if not all([self.smtp_user, self.smtp_password, self.alert_email]):
            logger.warning(
                "Email alerting not configured. Set SMTP_USER, SMTP_PASSWORD, and ALERT_EMAIL environment variables."
            )
            return False

        try:
            msg = MIMEText(message)
            msg["Subject"] = f"PhotoPrism-Google Photos Alert: {subject}"
            msg["From"] = self.smtp_user
            msg["To"] = self.alert_email

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email alert sent: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {str(e)}")
            return False

    def send_slack_alert(self, message: str) -> bool:
        """Send a Slack alert using incoming webhook.

        Args:
            message: Alert message

        Returns:
            bool: True if alert was sent successfully
        """
        if not self.slack_webhook_url:
            logger.warning("Slack alerting not configured. Set SLACK_WEBHOOK_URL environment variable.")
            return False

        try:
            response = requests.post(
                self.slack_webhook_url, json={"text": f"🔔 *PhotoPrism-Google Photos Alert*\n{message}"}
            )
            response.raise_for_status()

            logger.info("Slack alert sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {str(e)}")
            return False

    def send_telegram_alert(self, message: str) -> bool:
        """Send a Telegram alert.

        Args:
            message: Alert message

        Returns:
            bool: True if alert was sent successfully
        """
        if not all([self.telegram_bot_token, self.telegram_chat_id]):
            logger.warning(
                "Telegram alerting not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables."
            )
            return False

        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            response = requests.post(
                url,
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": f"🔔 PhotoPrism-Google Photos Alert\n\n{message}",
                    "parse_mode": "HTML",
                },
            )
            response.raise_for_status()

            logger.info("Telegram alert sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {str(e)}")
            return False

    def send_alert(self, subject: str, message: str, methods: Optional[list] = None) -> None:
        """Send alert through all configured methods or specified methods.

        Args:
            subject: Alert subject
            message: Alert message
            methods: List of alert methods to use ('email', 'slack', 'telegram'). If None, uses all configured methods.
        """
        available_methods = {
            "email": self.send_email_alert,
            "slack": self.send_slack_alert,
            "telegram": self.send_telegram_alert,
        }

        methods = methods or list(available_methods.keys())

        for method in methods:
            if method == "email":
                available_methods[method](subject, message)
            else:
                available_methods[method](message)
