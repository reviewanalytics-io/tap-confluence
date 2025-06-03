from typing import List

from singer_sdk import Tap
from singer_sdk.typing import PropertiesList, Property, StringType

from tap_confluence.streams import BlogpostsStream, PagesStream, SpacesStream

PLUGIN_NAME = "tap-confluence"

STREAM_TYPES = [SpacesStream, PagesStream, BlogpostsStream]


class TapConfluence(Tap):
    """confluence tap class."""

    name = "tap-confluence"
    config_jsonschema = PropertiesList(
        Property("site_name", StringType, required=True),
        Property("user_agent", StringType),
    ).to_dict()

    def discover_streams(self) -> List:
        """Return a list of discovered streams."""
        return [stream(tap=self) for stream in STREAM_TYPES]


cli = TapConfluence.cli
