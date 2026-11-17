from datetime import date, datetime

from ninja import Schema

from apps.items import ids


class ItemIn(Schema):
    url: str


class ItemSummaryOut(Schema):
    id: str
    url: str
    url_submitted: str
    status: str
    error: str
    title: str
    description: str
    author: str
    site_name: str
    published_at: date | None
    created_at: datetime
    fetched_at: datetime | None

    @staticmethod
    def resolve_id(obj):
        return ids.encode(obj.id)


class ItemOut(ItemSummaryOut):
    markdown: str
