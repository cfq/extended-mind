from ninja import NinjaAPI

api = NinjaAPI(version="1")


@api.get("/health")
def health(request):
    return {"status": "ok"}
