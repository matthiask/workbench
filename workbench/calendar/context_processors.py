from workbench.calendar.models import App, current_app


def app(request):
    return {"current_app": App.objects.filter(slug=current_app).first()}
