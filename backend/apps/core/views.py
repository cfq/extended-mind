from django.conf import settings
from django.http import FileResponse, Http404


def spa(request):
    # React Router handles the path; Django only hands over the shell.
    index = settings.FRONTEND_DIR / "index.html"
    if not index.exists():
        raise Http404
    return FileResponse(index.open("rb"), content_type="text/html")
