import pytest
from django.db import IntegrityError

from apps.users.models import User


def test_email_is_login_field():
    assert User.USERNAME_FIELD == "email"


@pytest.mark.django_db
def test_email_lowercased_on_save():
    user = User.objects.create(email="Mixed@Example.COM", username="mixed")

    user.refresh_from_db()
    assert user.email == "mixed@example.com"


@pytest.mark.django_db
def test_email_unique():
    User.objects.create(email="a@example.com", username="a")

    with pytest.raises(IntegrityError):
        User.objects.create(email="A@example.com", username="b")


@pytest.mark.django_db
def test_username_unique():
    User.objects.create(email="a@example.com", username="same")

    with pytest.raises(IntegrityError):
        User.objects.create(email="b@example.com", username="same")
