import json
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from tap_confluence.exceptions import (
    ConfluenceForbiddenException,
    ConfluenceRefreshCredentialsException,
    raise_for_error,
)

BASE_URL = "https://api.atlassian.com"
ACCESSIBLE_RESOURCES_URL = f"{BASE_URL}/oauth/token/accessible-resources"


class OauthStrategy:
    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        config_path: str | None = None,
    ):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._config_path = config_path

        self._session = requests.Session()

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "OauthStrategy":
        access_token = data.get("access_token")
        if not access_token:
            raise ValueError("Access token is required for OAuth strategy.")

        refresh_token = data.get("refresh_token")
        if not refresh_token:
            raise ValueError("Refresh token is required for OAuth strategy.")

        client_id = data.get("client_id")
        if not client_id:
            raise ValueError("Client ID is required for OAuth strategy.")

        client_secret = data.get("client_secret")
        if not client_secret:
            raise ValueError("Client secret is required for OAuth strategy.")

        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            config_path=data.get("config_path"),
        )

    def request(self, **kwargs):
        return self._request_with_retry(**kwargs, _retry_count=0)

    def _request_with_retry(self, **kwargs):
        _retry_count = kwargs.pop("_retry_count", 0)
        max_refresh_attempts = 1

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            with self._session.request(headers=headers, **kwargs) as response:
                if response.status_code == 401:
                    if _retry_count >= max_refresh_attempts:
                        raise_for_error(response)

                    self._refresh_credentials()
                    return self._request_with_retry(
                        **kwargs, _retry_count=_retry_count + 1
                    )

                raise_for_error(response)
                return response.json()
        except requests.RequestException as e:
            if e.response is not None:
                raise_for_error(e.response)

            raise e

    def _refresh_credentials(self) -> None:
        access_token, refresh_token = self._refresh_tokens()

        self._access_token = access_token
        self._refresh_token = refresh_token

        if self._config_path:
            try:
                with open(
                    self._config_path, "r", encoding="utf-8"
                ) as config_file:
                    config = json.load(config_file)
                    config.update(
                        {
                            "access_token": access_token,
                            "refresh_token": refresh_token,
                        }
                    )

                with open(
                    self._config_path, "w", encoding="utf-8"
                ) as config_file:
                    json.dump(config, config_file, indent=4)
            except Exception as e:
                raise ConfluenceRefreshCredentialsException(
                    f"Failed to update config file: {e}"
                ) from e

    def _refresh_tokens(self) -> tuple[str, str]:
        url = "https://auth.atlassian.com/oauth/token"
        result = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        }

        try:
            with requests.post(url, data=result, timeout=10) as response:
                raise_for_error(response)
                result = response.json()

                access_token = result.get("access_token")
                refresh_token = result.get("refresh_token")

                if not access_token or not refresh_token:
                    raise ConfluenceRefreshCredentialsException(
                        "Failed to refresh credentials", response
                    )

                return access_token, refresh_token
        except requests.RequestException as e:
            error_message = f"Failed to refresh credentials: {e}"

            if e.response is not None:
                raise ConfluenceRefreshCredentialsException(
                    error_message, e.response
                ) from e

            raise ConfluenceRefreshCredentialsException(error_message) from e
        except Exception as e:
            raise ConfluenceRefreshCredentialsException(
                f"Failed to refresh credentials: {e}"
            ) from e


class ConfluenceCursorPaginator:
    def __init__(self, items_key: str = "results"):
        self._cursor = None
        self._items_key = items_key

    def paginate(self, callback):
        while True:
            params = {"cursor": self.cursor} if self.cursor else {}
            response = callback(params)

            page = response.get(self._items_key, [])
            if not page:
                break

            yield page

            self._cursor = self._get_next_cursor(response)
            if not self._cursor:
                break

    @property
    def cursor(self):
        return self._cursor

    @staticmethod
    def _get_next_cursor(response: dict):
        try:
            next_link = response.get("_links", {}).get("next")

            if next_link:
                parsed = urlparse(next_link)
                query = parse_qs(parsed.query)

                return query.get("cursor", [None])[0]
        except Exception:  # pylint: disable=broad-except
            # self.logger.error("Error extracting next page token: %s", e)

            return None

        return None


class Confluence:
    _cloud_id: str | None = None

    def __init__(
        self,
        oauth: dict[str, str],
        site_name: str,
    ):
        self._strategy = OauthStrategy.from_dict(oauth)
        self._site_name = site_name

    def timezone(self):
        result = self.request(url="/rest/api/2/myself", method="GET")

        return result.get("timeZone")

    def space_blogposts(self, space_id: str, limit: int = 100):
        url = f"/wiki/api/v2/spaces/{space_id}/blogposts"
        base_params = {
            "body-format": "storage",
            "sort": "-modified-date",
            "limit": limit,
        }

        paginator = ConfluenceCursorPaginator()
        pages = paginator.paginate(
            lambda params: self.request(
                url=url,
                method="GET",
                params={**params, **base_params},
            )
        )

        for page in pages:
            yield page, paginator.cursor

    def space_pages(self, space_id: str, limit: int = 100):
        url = f"/wiki/api/v2/spaces/{space_id}/pages"
        base_params = {
            "body-format": "storage",
            "sort": "-modified-date",
            "limit": limit,
        }

        paginator = ConfluenceCursorPaginator()
        pages = paginator.paginate(
            lambda params: self.request(
                url=url,
                method="GET",
                params={**params, **base_params},
            )
        )

        for page in pages:
            yield page, paginator.cursor

    def spaces(self):
        yield from ConfluenceCursorPaginator().paginate(self._fetch_spaces)

    def _fetch_spaces(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.request(
            url="/wiki/api/v2/spaces",
            method="GET",
            params=params,
        )

    def request(self, url: str, **kwargs):
        if not self._cloud_id:
            self._cloud_id = self._get_cloud_id_or_fail()

        url = f"{BASE_URL}/ex/confluence/{self._cloud_id}{url}"
        return self._strategy.request(
            url=url,
            **kwargs,
        )

    def _get_cloud_id_or_fail(self) -> str:
        if self._cloud_id:
            return self._cloud_id

        resources = self._strategy.request(
            url=ACCESSIBLE_RESOURCES_URL,
            method="GET",
        )
        resource = next(
            (
                resource
                for resource in resources
                if resource.get("name") == self._site_name
            ),
            None,
        )

        cloud_id = resource.get("id") if resource else None
        if not cloud_id:
            raise ConfluenceForbiddenException(
                f"Invalid or unauthorized site name: {self._site_name}"
            )

        return str(cloud_id)
