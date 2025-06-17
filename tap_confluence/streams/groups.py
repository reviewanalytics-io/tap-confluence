import re
from singer.catalog import CatalogEntry
import singer.metadata as metadata_utils

from tap_confluence.context import Context
from tap_confluence.streams.base import (
    BaseStream,
    SpaceStream,
    StreamGroup,
    StreamGroupType,
)
from tap_confluence.streams.space.blogpost import BlogpostStream
from tap_confluence.streams.space.page import PageStream


SPACE_STREAM_GROUP_PATTERN = r"^space_(?P<space_id>.+)$"


def _get_selected_streams(entry: CatalogEntry) -> list[str]:
    metadata = metadata_utils.to_map(entry.metadata)
    if not metadata:
        return []

    selected = []

    for breadcrumb, value in metadata.items():
        if len(breadcrumb) != 2 or breadcrumb[0] != "properties":
            continue

        (_, stream_name) = breadcrumb
        if value.get("selected"):
            selected.append(stream_name)

    return selected


class SpaceStreamGroup(StreamGroup):
    @property
    def group_type(self) -> StreamGroupType:
        return StreamGroupType.SPACE

    @property
    def streams(self) -> dict[str, type[SpaceStream]]:
        return {"pages": PageStream, "blogposts": BlogpostStream}

    def build_streams(
        self, entry: CatalogEntry, context: Context
    ) -> list[BaseStream]:
        if not entry.tap_stream_id or not entry.metadata:
            return []

        selected_streams = _get_selected_streams(entry)
        if not selected_streams:
            return []

        match = re.match(SPACE_STREAM_GROUP_PATTERN, entry.tap_stream_id)
        if not match:
            return []

        (space_id,) = match.groups()

        streams = []

        for stream_name in selected_streams:
            stream_class = self.streams.get(stream_name)
            if not stream_class:
                continue

            stream_id = f"{entry.tap_stream_id}_{stream_name}"
            streams.append(stream_class(space_id, stream_id, context))

        return streams


STREAM_GROUPS = [
    SpaceStreamGroup(),
]

STREAM_GROUPS_BY_TYPE = {group.group_type: group for group in STREAM_GROUPS}
