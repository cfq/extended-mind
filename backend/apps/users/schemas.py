from datetime import datetime

from ninja import Schema


class SignupIn(Schema):
    email: str
    username: str
    password: str


class LoginIn(Schema):
    email: str
    password: str


class UserOut(Schema):
    username: str
    email: str


class TokenIn(Schema):
    name: str


class TokenOut(Schema):
    id: int
    name: str
    hint: str
    created_at: datetime
    last_used_at: datetime | None


class TokenCreatedOut(TokenOut):
    # Only ever returned here, on creation.
    key: str
