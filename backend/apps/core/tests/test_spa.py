import pytest


@pytest.fixture
def frontend(settings, tmp_path):
    (tmp_path / "index.html").write_text("<div id=root></div>")
    settings.FRONTEND_DIR = tmp_path
    return tmp_path


@pytest.mark.parametrize("path", ["/", "/login", "/item/abc", "/user/test"])
def test_serves_index_for_app_routes(client, frontend, path):
    response = client.get(path)

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"<div id=root></div>"


def test_404_without_build(client, settings, tmp_path):
    settings.FRONTEND_DIR = tmp_path

    assert client.get("/").status_code == 404


@pytest.mark.parametrize("path", ["/api/nope", "/static/nope.css"])
def test_reserved_prefixes_not_served_index(client, frontend, path):
    assert client.get(path).status_code == 404


def test_admin_not_served_index(client, frontend):
    response = client.get("/admin/")

    # Admin redirects to its own login page.
    assert response.status_code == 302
    assert "/admin/login/" in response.url
