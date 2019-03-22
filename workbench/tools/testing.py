from django.contrib.messages import get_messages


def messages(response):
    return [m.message for m in get_messages(response.wsgi_request)]
