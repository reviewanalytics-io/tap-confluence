from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qs, urlparse

import requests
from singer_sdk.exceptions import RetriableAPIError
from singer_sdk.streams import RESTStream

from tap_confluence.authenticator import ConfluenceAuthenticator

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class ConfluenceStream(RESTStream):
    limit = 100

    @property
    def authenticator(self) -> ConfluenceAuthenticator:
        """Return the authenticator for this stream."""
        return ConfluenceAuthenticator(self)

    @property
    def url_base(self) -> str:
        """Return the base Confluence URL."""

        cloud_id = self.authenticator.cloud_id
        return f"https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/api/v2"

    @property
    def schema_filepath(self) -> Path:
        """Return the schema file path."""

        return SCHEMAS_DIR / f"{self.name}.json"

    def get_url_params(
        self, context: Mapping[str, Any] | None, next_page_token: Any | None
    ) -> dict[str, Any] | str:
        params = {
            "limit": self.limit,
        }

        if next_page_token:
            params["cursor"] = next_page_token

        return params

    def parse_response(self, response: requests.Response) -> Iterable[dict]:
        json = response.json()

        yield from json.get("results", [])

    def validate_response(self, response: requests.Response) -> None:
        msg = (
            f"{response.status_code} Status Code"
            f"(Reason: {response.reason}/{response.text}) for path {response.url}"
        )

        if response.status_code != 200:
            self.logger.error(msg)

        if response.status_code == 401:
            self.logger.warning("Authentication failed; refreshing credentials...")

            self.authenticator.update_credentials()

            raise RetriableAPIError(
                msg,
                response,
            )

        if response.status_code == 429:
            self.logger.warning("Rate limit exceeded. Retrying after a delay...")

            raise RetriableAPIError(msg, response)

        super().validate_response(response)

    def get_next_page_token(
        self,
        response: requests.Response,
        _: Any | None = None,
    ) -> Any | None:
        """Return the next page token."""

        data = response.json()

        try:
            next_link = data.get("_links", {}).get("next")

            if next_link:
                parsed = urlparse(next_link)
                query = parse_qs(parsed.query)

                return query.get("cursor", [None])[0]
        except Exception as e:  # pylint: disable=broad-except
            self.logger.error("Error extracting next page token: %s", e)

            return None

        return None


class SpacesStream(ConfluenceStream):
    name = "spaces"
    path = "/spaces"

    primary_keys = ["id"]  # type: ignore

    def get_url_params(
        self, context: Mapping[str, Any] | None, next_page_token: Any | None
    ) -> dict[str, Any] | str:
        params = super().get_url_params(context, next_page_token)

        if isinstance(params, dict):
            params["description-format"] = "plain"

        return params


class PagesStream(ConfluenceStream):
    name = "pages"
    path = "/pages"

    primary_keys = ["id"]  # type: ignore

    def get_url_params(
        self, context: Mapping[str, Any] | None, next_page_token: Any | None
    ) -> dict[str, Any] | str:
        params = super().get_url_params(context, next_page_token)

        if isinstance(params, dict):
            params["body-format"] = "storage"
            params["sort"] = "-modified-date"

        return params


class BlogpostsStream(ConfluenceStream):
    name = "blogposts"
    path = "/blogposts"

    primary_keys = ["id"]  # type: ignore

    def get_url_params(
        self, context: Mapping[str, Any] | None, next_page_token: Any | None
    ) -> dict[str, Any] | str:
        params = super().get_url_params(context, next_page_token)

        if isinstance(params, dict):
            params["body-format"] = "storage"
            params["sort"] = "-modified-date"

        return params
