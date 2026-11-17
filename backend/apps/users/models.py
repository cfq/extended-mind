import hashlib
import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        super().save(*args, **kwargs)


class ApiToken(models.Model):
    """Bearer token for scripts and the iOS Shortcut.

    Only a SHA-256 of the key is stored; the key itself is shown once,
    on creation. Keys are random, so a plain hash is enough: no salt or
    slow hash needed.
    """

    PREFIX = "em_"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tokens")
    name = models.CharField(max_length=100)
    # Start of the key, so tokens can be told apart in lists.
    hint = models.CharField(max_length=16)
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.hint}…)"

    @staticmethod
    def hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def create(cls, user: User, name: str) -> tuple[ApiToken, str]:
        key = cls.PREFIX + secrets.token_urlsafe(32)
        token = cls.objects.create(
            user=user, name=name, hint=key[:8], key_hash=cls.hash(key)
        )
        return token, key
