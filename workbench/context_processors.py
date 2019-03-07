from django.conf import settings


def workbench(request):
    return {"WORKBENCH": settings.WORKBENCH}
