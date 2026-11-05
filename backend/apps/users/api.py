from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from ninja import Router, Status
from ninja.errors import HttpError
from ninja.security import django_auth

from apps.users.models import User
from apps.users.schemas import LoginIn, SignupIn, UserOut

auth_router = Router()
users_router = Router(auth=django_auth)


@auth_router.get("/csrf", response={204: None})
def csrf(request):
    # Sets the csrftoken cookie the SPA sends back as X-CSRFToken.
    get_token(request)
    return Status(204, None)


@auth_router.post("/signup", response={201: UserOut})
def signup(request, data: SignupIn):
    if not settings.SIGNUP_ENABLED:
        raise HttpError(403, "Signups are disabled.")
    user = User(email=data.email.lower(), username=data.username)
    try:
        user.full_clean(exclude=["password"])
        validate_password(data.password, user)
    except ValidationError as e:
        raise HttpError(400, " ".join(e.messages)) from e
    user.set_password(data.password)
    user.save()
    return Status(201, user)


@auth_router.post("/login", response=UserOut)
def login_view(request, data: LoginIn):
    user = authenticate(request, username=data.email.lower(), password=data.password)
    if user is None:
        raise HttpError(401, "Wrong email or password.")
    login(request, user)
    return user


@auth_router.post("/logout", response={204: None})
def logout_view(request):
    logout(request)
    return Status(204, None)


@auth_router.get("/session", response=UserOut)
def session(request):
    if not request.user.is_authenticated:
        raise HttpError(401, "Not logged in.")
    return request.user


@users_router.get("/{username}", response=UserOut)
def user_detail(request, username: str):
    return get_object_or_404(User, username=username)
