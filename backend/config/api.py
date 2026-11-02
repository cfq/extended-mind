from ninja import NinjaAPI

from apps.core.api import router as core_router
from apps.users.api import auth_router, users_router

api = NinjaAPI(version="1")
api.add_router("/", core_router)
api.add_router("/auth", auth_router)
api.add_router("/users", users_router)
