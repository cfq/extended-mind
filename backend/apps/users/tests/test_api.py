import pytest
from django.test import Client

from apps.users.models import User
from conftest import PASSWORD

SIGNUP = "/api/v1/auth/signup"
LOGIN = "/api/v1/auth/login"


def post(client, url, data=None):
    return client.post(url, data or {}, content_type="application/json")


@pytest.fixture
def signup_enabled(settings):
    settings.SIGNUP_ENABLED = True


# Signup


def test_signup_creates_user(client, db, signup_enabled):
    response = post(
        client,
        SIGNUP,
        {"email": "New@Example.com", "username": "new", "password": PASSWORD},
    )

    assert response.status_code == 201
    assert response.json() == {"username": "new", "email": "new@example.com"}
    assert User.objects.get(username="new").check_password(PASSWORD)


def test_signup_disabled(client, db, settings):
    settings.SIGNUP_ENABLED = False

    response = post(
        client,
        SIGNUP,
        {"email": "a@example.com", "username": "a", "password": PASSWORD},
    )

    assert response.status_code == 403
    assert not User.objects.exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "TEST@example.com", "username": "fresh", "password": PASSWORD},
        {"email": "fresh@example.com", "username": "test", "password": PASSWORD},
        {"email": "not-an-email", "username": "fresh", "password": PASSWORD},
        {"email": "fresh@example.com", "username": "fresh", "password": "123"},
    ],
    ids=["duplicate-email", "duplicate-username", "invalid-email", "weak-password"],
)
def test_signup_rejects(client, payload, signup_enabled, user):
    response = post(client, SIGNUP, payload)

    assert response.status_code == 400
    assert response.json()["detail"]
    assert not User.objects.filter(username="fresh").exists()


# Login, logout, session


def test_login(client, user):
    response = post(client, LOGIN, {"email": "test@example.com", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["username"] == "test"
    assert client.session["_auth_user_id"] == str(user.pk)


def test_login_email_case_insensitive(client, user):
    response = post(client, LOGIN, {"email": "TEST@Example.com", "password": PASSWORD})

    assert response.status_code == 200


@pytest.mark.parametrize(
    "email, password",
    [("test@example.com", "wrong"), ("nobody@example.com", PASSWORD)],
    ids=["wrong-password", "unknown-email"],
)
def test_login_fails(client, user, email, password):
    response = post(client, LOGIN, {"email": email, "password": password})

    assert response.status_code == 401
    assert "_auth_user_id" not in client.session


def test_logout(user_client):
    response = post(user_client, "/api/v1/auth/logout")

    assert response.status_code == 204
    assert "_auth_user_id" not in user_client.session


def test_session_logged_in(user_client):
    response = user_client.get("/api/v1/auth/session")

    assert response.status_code == 200
    assert response.json() == {"username": "test", "email": "test@example.com"}


def test_session_logged_out(client, db):
    assert client.get("/api/v1/auth/session").status_code == 401


def test_csrf_sets_cookie(client):
    response = client.get("/api/v1/auth/csrf")

    assert response.status_code == 204
    assert "csrftoken" in response.cookies


def test_csrf_enforced_on_authenticated_post(user, app):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    response = post(client, "/api/v1/items", {"url": "https://example.com"})

    assert response.status_code == 403


# Users


def test_user_detail(user_client, other_user):
    response = user_client.get("/api/v1/users/other")

    assert response.status_code == 200
    assert response.json() == {"username": "other", "email": "other@example.com"}


def test_user_detail_unknown(user_client):
    assert user_client.get("/api/v1/users/nobody").status_code == 404


def test_user_detail_requires_login(client, user):
    assert client.get("/api/v1/users/test").status_code == 401
