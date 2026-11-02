from django.contrib import admin
from django.urls import path, re_path

from apps.core.views import spa
from config.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
    re_path(r"^(?!(api|admin|static)(/|$)).*$", spa),
]
