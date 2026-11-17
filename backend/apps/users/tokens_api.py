from django.shortcuts import get_object_or_404
from ninja import Router, Status
from ninja.errors import HttpError
from ninja.security import django_auth

from apps.users.models import ApiToken
from apps.users.schemas import TokenCreatedOut, TokenIn, TokenOut

# Session only: a token can't mint or revoke tokens.
router = Router(auth=django_auth)


@router.get("", response=list[TokenOut])
def list_tokens(request):
    return ApiToken.objects.filter(user=request.user)


@router.post("", response={201: TokenCreatedOut})
def create_token(request, data: TokenIn):
    name = data.name.strip()
    if not name:
        raise HttpError(400, "Give the token a name.")
    token, key = ApiToken.create(request.user, name[:100])
    token.key = key
    return Status(201, token)


@router.delete("/{token_id}", response={204: None})
def delete_token(request, token_id: int):
    get_object_or_404(ApiToken, id=token_id, user=request.user).delete()
    return Status(204, None)
