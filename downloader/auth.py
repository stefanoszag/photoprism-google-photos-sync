import requests

from . import config


def get_token(photoprism_url):
    if not config.USERNAME or not config.PASSWORD:
        raise Exception("Environment variables PHOTOPRISM_USERNAME and PHOTOPRISM_PASSWORD must be set.")
    url = f"{photoprism_url}/api/v1/session"
    payload = {"username": config.USERNAME, "password": config.PASSWORD}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise an error for bad responses
        token = response.json().get("access_token")
        if not token:
            raise Exception("Login failed, no token received.")
        return token
    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        raise
