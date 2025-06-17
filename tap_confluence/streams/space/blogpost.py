from tap_confluence.streams.base import SpaceStream


class BlogpostStream(SpaceStream):
    @property
    def name(self) -> str:
        return "blogposts"

    @property
    def primary_keys(self) -> list[str]:
        return ["id"]

    def sync(self) -> None:
        for page, _ in self.context.confluence.space_blogposts(self.space_id):
            self.write_page(page)
