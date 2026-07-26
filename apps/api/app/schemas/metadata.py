from app.schemas.common import ApiSchema


class TaxonomyItem(ApiSchema):
    id: int
    name: str
    slug: str
