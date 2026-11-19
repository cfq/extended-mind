import shutil
from pathlib import Path

import pytest
from django.core.management import call_command
from procrastinate import testing
from procrastinate.contrib.django import procrastinate_app

from apps.items.models import Item
from apps.users.models import User

FIXTURES = Path(__file__).parent / "apps" / "items" / "fixtures"
PASSWORD = "testpass123"


@pytest.fixture
def data(db):
    call_command("loaddata", "test_users", "test_items", verbosity=0)


@pytest.fixture
def user(data):
    return User.objects.get(username="test")


@pytest.fixture
def other_user(data):
    return User.objects.get(username="other")


@pytest.fixture
def user_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def item(data):
    # "Handles are the better pointers", has an HTML source.
    return Item.objects.get(id="01a1a417-604d-7679-9ecf-8b8932f3091c")


@pytest.fixture
def item_sources_dir(settings, tmp_path):
    """ITEM_SOURCES_DIR in tmp, seeded with the fixture HTML files."""
    path = tmp_path / "item_sources"
    shutil.copytree(FIXTURES / "item_sources", path)
    settings.ITEM_SOURCES_DIR = path
    return path


@pytest.fixture
def fixture_html():
    def read(item_id: str) -> bytes:
        (path,) = (FIXTURES / "item_sources" / item_id).glob("*.html")
        return path.read_bytes()

    return read


@pytest.fixture
def app():
    """Procrastinate with an in-memory queue: deferred jobs, no worker."""
    with procrastinate_app.current_app.replace_connector(
        testing.InMemoryConnector()
    ) as app:
        yield app


@pytest.fixture(autouse=True)
def no_browser(settings):
    """No browser unless a test sets BROWSER_URL (and fakes browser.visit)."""
    settings.BROWSER_URL = ""
