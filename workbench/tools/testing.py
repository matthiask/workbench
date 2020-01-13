from django.contrib.messages import get_messages


def messages(response):
    return [m.message for m in get_messages(response.wsgi_request)]


def check_code(test, base_url):
    def code(param, status_code=200):
        response = test.client.get("{}?{}".format(base_url, param))
        test.assertEqual(response.status_code, status_code)

    return code
