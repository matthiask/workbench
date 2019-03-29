from django.http import HttpResponse

from workbench.projects.models import Service


def set_order(request):
    for index, id in enumerate(request.POST.getlist("ids[]")):
        Service.objects.filter(id=id).update(position=10 * (index + 1))
    return HttpResponse("OK", status=202)  # Accepted
