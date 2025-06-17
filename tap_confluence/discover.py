from itertools import chain

from singer.catalog import Catalog, CatalogEntry, Schema

from tap_confluence import utils
from tap_confluence.context import Context


SPACE_SCHEMA_NAME = "spaces"


def run(context: Context) -> Catalog:
    catalog = Catalog([])

    schema = Schema.from_dict(utils.load_schema(SPACE_SCHEMA_NAME))
    metadata = utils.build_schema_metadata(
        schema, additional_properties={"group": "space"}
    )

    spaces = chain.from_iterable(context.confluence.spaces())

    for space in spaces:
        stream_id = f"space_{space['id']}"
        stream_name = f"{space['name']} ({space['key']})"

        entry = CatalogEntry(
            tap_stream_id=stream_id,
            stream=stream_name,
            schema=schema,
            metadata=metadata,
        )
        catalog.streams.append(entry)

    return catalog
