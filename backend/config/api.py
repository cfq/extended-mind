from ninja import NinjaAPI

from apps.core.api import router as core_router

api = NinjaAPI(version="1")
api.add_router("/", core_router)
