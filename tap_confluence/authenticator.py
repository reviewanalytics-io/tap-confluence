import json
import logging
from typing import Any

import requests
from singer_sdk.authenticators import APIAuthenticatorBase, SingletonMeta

from tap_confluence.exceptions import ConfluenceException

logger = logging.getLogger(__name__)

CONFIG_FILE_PATH = "config.json"


class ConfluenceAuthenticator(APIAuthenticatorBase, metaclass=SingletonMeta):
    def __init__(self, stream: Any) -> None:
        super().__init__(stream)

        self.site_name = stream.config.get("site_name")
        self.access_token = self.config.get("access_token")
        self.refresh_token = self.config.get("refresh_token")
        self.oauth_client_id = self.config.get("client_id")
        self.oauth_client_secret = self.config.get("client_secret")
        self.cloud_id = self._get_cloud_id()
        if not self.cloud_id:
            raise ConfluenceException(
                f"Could not find cloud ID for site '{self.site_name}'. "
                "Please check your site name and Confluence API access."
            )

        logger.info(
            "Confluence authenticator initialized for site '%s' (cloud ID: %s)",
            self.site_name,
            self.cloud_id,
        )

    def authenticate_request(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        request.headers["Authorization"] = f"Bearer {self.access_token}"

        return super().authenticate_request(request)

    def _get_cloud_id(self) -> str | None:
        try:
            logger.info("Fetching cloud ID for site '%s'", self.site_name)

            url = "https://api.atlassian.com/oauth/token/accessible-resources"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            }

            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            for resource in response.json():
                if resource.get("name") == self.site_name:
                    return resource.get("id")

            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.warning("Access token expired, refreshing token...")

                self.update_credentials()
                return self._get_cloud_id()

            raise e

    def update_credentials(self):
        logger.info("Refreshing OAuth token")

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.oauth_client_id,
            "client_secret": self.oauth_client_secret,
            "refresh_token": self.refresh_token,
        }

        response = None

        try:
            response = requests.post(
                "https://auth.atlassian.com/oauth/token", data=payload, timeout=60
            )
            logger.info("Response from Atlassian: %s", response.text)
            response.raise_for_status()

            result = response.json()

            self.access_token = result["access_token"]
            self.refresh_token = result["refresh_token"]

            self._update_config(result)
        except Exception as e:
            error_message = str(e)

            if response is not None:
                error_message = f"{error_message}, Response from Atlassian: " f"{response.text}"

            raise ConfluenceException(error_message) from e

    def _update_config(self, update: dict):
        """Update the config file with the new access token."""

        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as config_file:
                config = json.load(config_file)
                config.update(update)

            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as config_file:
                json.dump(config, config_file, indent=4)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error updating config file: %s", e)
