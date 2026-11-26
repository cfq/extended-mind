"""Model tags: a small LLM run locally by Ollama, no external service.

The model reads the start of the article and the user's tags, and
suggests up to MAX_TAGS, reusing the user's tags where they fit.
"""

import json

import httpx2
from django.conf import settings
from django.db.models import Count

from apps.items import tagging
from apps.items.models import Item, ItemTag

MAX_TAGS = 3
# Shorter is faster on CPU; the opening says what an article is about.
DOC_CHARS = 2500
# Most used first; more would crowd the 3B model's context.
MAX_KNOWN_TAGS = 200
# CPU only: loading the model plus a reply can take a while.
TIMEOUT = 300
# How long Ollama keeps the model in memory after a request.
KEEP_ALIVE = "5m"

SYSTEM = """\
You tag saved web articles for a personal archive.
Reply with up to 3 tags for the main topics of the article.
- Prefer tags from the user's existing tags when they fit.
- A new tag is a short, general topic of 1 to 3 words, like "typography" \
or "urban-planning". Not a name of a person, a date, or a site.
- Lowercase, words joined by hyphens.
- Fewer tags is better than a weak tag. Reply with no tags if none fit."""

SCHEMA = {
    "type": "object",
    "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
    "required": ["tags"],
}


def text(item: Item) -> str:
    return item.detail.search_text() if item.detail else ""


def document(item: Item) -> str:
    parts = [
        f"Title: {item.title}" if item.title else "",
        f"Description: {item.description}" if item.description else "",
        text(item)[:DOC_CHARS],
    ]
    return "\n\n".join(p for p in parts if p)


def known_tags(item: Item) -> list[str]:
    tags = (
        item.user.tags.annotate(n=Count("item_tags"))
        .filter(n__gt=0)
        .order_by("-n", "name")
    )
    return list(tags.values_list("name", flat=True)[:MAX_KNOWN_TAGS])


def prompt(item: Item) -> str:
    # The tag list after the article: the small model reuses it more there.
    known = ", ".join(known_tags(item)) or "(none yet)"
    return (
        f"Article:\n{document(item)}\n\n"
        f"Existing tags (reuse these when they fit): {known}"
    )


def chat(system: str, user: str) -> list[str]:
    """The model's tags, raw. Raises on HTTP errors or a bad reply."""
    response = httpx2.post(
        f"{settings.OLLAMA_URL}/api/chat",
        json={
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": SCHEMA,
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0, "num_ctx": 4096},
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    tags = json.loads(response.json()["message"]["content"])["tags"]
    return [t for t in tags if isinstance(t, str)]


def suggest(item: Item) -> list[str]:
    """Tag names (normalised) for the item, best first."""
    # MAX_TAGS is per item, so running again doesn't pile on more.
    budget = MAX_TAGS - item.item_tags.filter(source=ItemTag.Source.MODEL).count()
    if budget <= 0 or not settings.OLLAMA_URL or not text(item).strip():
        return []
    # Already on the item, or removed from it: don't spend a slot on them.
    taken = set(item.item_tags.values_list("tag__name", flat=True))
    taken |= set(item.tag_removals.values_list("name", flat=True))
    names: list[str] = []
    for raw in chat(SYSTEM, prompt(item)):
        name = tagging.normalize(raw)
        if name and name not in taken and name not in names:
            names.append(name)
    return names[:budget]


def autotag(item: Item) -> list[ItemTag]:
    return tagging.add_tags(item, suggest(item), ItemTag.Source.MODEL)
