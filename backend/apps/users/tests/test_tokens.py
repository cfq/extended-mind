import pytest
from django.test import Client

from apps.items import ids
from apps.items.models import Item
from apps.users.models import ApiToken

TOKENS = "/api/v1/tokens"
ITEMS = "/api/v1/items"


@pytest.fixture
def key(user):
    return ApiToken.create(user, "Phone")[1]


def bearer(key):
    return {"HTTP_AUTHORIZATION": f"Bearer {key}"}


# Model


def test_create_stores_only_a_hash(user):
    token, key = ApiToken.create(user, "Phone")

    assert key.startswith("em_")
    assert len(key) > 40
    assert token.hint == key[:8]
    assert token.key_hash == ApiToken.hash(key)
    assert key not in token.key_hash


def test_keys_are_unique(user):
    assert ApiToken.create(user, "a")[1] != ApiToken.create(user, "b")[1]


# Token endpoints


def test_create_token(user_client, user):
    response = user_client.post(
        TOKENS, {"name": " Phone "}, content_type="application/json"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Phone"
    assert body["key"].startswith(body["hint"])
    assert ApiToken.objects.get(id=body["id"]).user == user


def test_create_token_needs_a_name(user_client):
    response = user_client.post(TOKENS, {"name": "  "}, content_type="application/json")

    assert response.status_code == 400
    assert not ApiToken.objects.exists()


def test_list_own_tokens_without_keys(user_client, user, other_user):
    ApiToken.create(user, "Phone")
    ApiToken.create(other_user, "Theirs")

    response = user_client.get(TOKENS)

    assert response.status_code == 200
    assert [t["name"] for t in response.json()] == ["Phone"]
    assert "key" not in response.json()[0]
    assert "key_hash" not in response.json()[0]


def test_delete_token(user_client, user, key):
    token = ApiToken.objects.get()

    assert user_client.delete(f"{TOKENS}/{token.id}").status_code == 204
    assert not ApiToken.objects.exists()


def test_delete_other_users_token(user_client, other_user):
    token, _ = ApiToken.create(other_user, "Theirs")

    assert user_client.delete(f"{TOKENS}/{token.id}").status_code == 404
    assert ApiToken.objects.filter(pk=token.pk).exists()


@pytest.mark.parametrize(
    "method, path", [("get", TOKENS), ("post", TOKENS), ("delete", f"{TOKENS}/1")]
)
def test_token_endpoints_require_session(client, key, method, path):
    # A token can't be used to list, mint or revoke tokens.
    response = getattr(client, method)(path, **bearer(key))

    assert response.status_code == 401


# Bearer auth on items


def test_create_item_with_token(client, user, key, app):
    # CSRF checks on: bearer requests don't need a CSRF token.
    client = Client(enforce_csrf_checks=True)

    response = client.post(
        ITEMS,
        {"url": "https://example.com/?utm_source=x"},
        content_type="application/json",
        **bearer(key),
    )

    assert response.status_code == 201
    item = Item.objects.get(id=ids.decode(response.json()["id"]))
    assert item.user == user
    assert item.url == "https://example.com/"
    assert len(app.connector.jobs) == 1


def test_list_items_with_token(client, key):
    response = client.get(ITEMS, **bearer(key))

    assert response.status_code == 200
    assert len(response.json()) == 5


def test_token_sees_only_own_items(client, other_user, item):
    _, key = ApiToken.create(other_user, "Theirs")

    response = client.get(f"{ITEMS}/{ids.encode(item.id)}", **bearer(key))

    assert response.status_code == 404


def test_use_sets_last_used_at(client, key):
    assert ApiToken.objects.get().last_used_at is None

    client.get(ITEMS, **bearer(key))

    assert ApiToken.objects.get().last_used_at is not None


@pytest.mark.parametrize(
    "header",
    ["Bearer em_wrong", "Bearer ", "Token {key}", "{key}"],
    ids=["unknown", "empty", "wrong-scheme", "no-scheme"],
)
def test_bad_token_rejected(client, key, header):
    response = client.get(ITEMS, HTTP_AUTHORIZATION=header.format(key=key))

    assert response.status_code == 401


def test_bad_token_on_post_says_so(client, key):
    response = client.post(
        ITEMS,
        {"url": "https://example.com"},
        content_type="application/json",
        **bearer("em_wrong"),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or revoked token."


def test_deleted_token_rejected(client, key):
    ApiToken.objects.all().delete()

    assert client.get(ITEMS, **bearer(key)).status_code == 401


def test_inactive_user_token_rejected(client, user, key):
    user.is_active = False
    user.save()

    assert client.get(ITEMS, **bearer(key)).status_code == 401


def test_session_without_csrf_still_rejected(user, data):
    # Adding bearer auth mustn't loosen CSRF for session requests.
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    response = client.post(
        ITEMS, {"url": "https://example.com"}, content_type="application/json"
    )

    assert response.status_code in (401, 403)
    assert not Item.objects.filter(url="https://example.com").exists()
