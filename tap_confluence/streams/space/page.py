from tap_confluence.streams.base import SpaceStream


class PageStream(SpaceStream):
    @property
    def name(self) -> str:
        return "pages"

    @property
    def primary_keys(self) -> list[str]:
        return ["id"]

    def sync(self) -> None:
        for page, _ in self.context.confluence.space_pages(self.space_id):
            self.write_page(page)
