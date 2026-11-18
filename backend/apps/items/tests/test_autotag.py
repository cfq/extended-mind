import pytest

from apps.items import autotag, tagging
from apps.items.models import ItemTag, Tag

MODEL = ItemTag.Source.MODEL
MANUAL = ItemTag.Source.MANUAL


@pytest.fixture
def replies(monkeypatch):
    """Fake model: returns the queued replies, records the prompts."""
    queue: list[list[str]] = []
    prompts: list[str] = []

    def chat(system, user):
        prompts.append(user)
        return queue.pop(0)

    monkeypatch.setattr(autotag, "chat", chat)
    return queue, prompts


def tags_of(item):
    return {link.tag.name: link.source for link in item.item_tags.all()}


def test_adds_normalised_model_tags(item, replies):
    queue, _ = replies
    queue.append(["Memory Management", "data oriented design", "C++"])

    autotag.autotag(item)

    assert tags_of(item) == {
        "memory-management": MODEL,
        "data-oriented-design": MODEL,
        "c++": MODEL,
    }


def test_caps_and_drops_junk(item, replies):
    queue, _ = replies
    queue.append(["日本", "a", "a", "b", "c", "d"])

    assert autotag.suggest(item) == ["a", "b", "c"]


def test_skips_tags_on_item_or_removed(item, replies):
    queue, _ = replies
    tagging.add_tags(item, ["pointers"], MANUAL)
    tagging.add_tags(item, ["segfaults"], MODEL)
    tagging.remove_tag(item, Tag.objects.get(name="segfaults"))
    queue.append(["pointers", "segfaults", "memory"])

    assert autotag.suggest(item) == ["memory"]


def test_prompt_lists_tags_in_use_most_used_first(item, user, replies):
    queue, prompts = replies
    others = user.items.exclude(pk=item.pk)[:2]
    for other in others:
        tagging.add_tags(other, ["programming"], MANUAL)
    tagging.add_tags(others[0], ["art"], MANUAL)
    tagging.get_or_create_tag(user, "unused")
    queue.append([])

    autotag.autotag(item)

    assert "Handles are the better pointers" in prompts[0]
    assert prompts[0].endswith(": programming, art")


def test_running_again_adds_no_more(item, replies):
    queue, prompts = replies
    queue.append(["a", "b", "c"])
    autotag.autotag(item)

    assert autotag.autotag(item) == []
    assert len(prompts) == 1


def test_no_text_or_no_server_skips_model(item, replies, settings):
    _, prompts = replies
    settings.OLLAMA_URL = ""
    assert autotag.suggest(item) == []

    settings.OLLAMA_URL = "http://ollama:11434"
    item.text = " "
    assert autotag.suggest(item) == []
    assert prompts == []


def test_chat_reads_structured_reply(monkeypatch, settings):
    settings.OLLAMA_URL = "http://ollama.test"
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": '{"tags": ["art", 3, "design"]}'}}

    def post(url, json, timeout):
        sent.update(url=url, body=json)
        return Response()

    monkeypatch.setattr(autotag.httpx2, "post", post)

    assert autotag.chat("system", "user") == ["art", "design"]
    assert sent["url"] == "http://ollama.test/api/chat"
    assert sent["body"]["model"] == settings.OLLAMA_MODEL
    assert sent["body"]["format"] == autotag.SCHEMA
