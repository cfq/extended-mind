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
