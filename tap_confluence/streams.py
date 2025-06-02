from base64 import b64encode
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qs, urlparse

import requests
from singer_sdk.streams import RESTStream

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class ConfluenceStream(RESTStream):
    limit = 100

    @property
    def url_base(self) -> str:
        """Return the base Confluence URL."""

        site_name = self.config.get("site_name")
        return f"https://{site_name}.atlassian.net/wiki/api/v2"

    @property
    def schema_filepath(self) -> Path:
        """Return the schema file path."""

        return SCHEMAS_DIR / f"{self.name}.json"

    @property
    def http_headers(self) -> dict:
        result = super().http_headers

        email = self.config.get("email")
        api_token = self.config.get("api_token")
        auth = b64encode(f"{email}:{api_token}".encode()).decode()

        result["Authorization"] = f"Basic {auth}"

        return result

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
