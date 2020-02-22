from django.test import TestCase

from freezegun import freeze_time

from workbench import factories
from workbench.timer.models import TimerState, Timestamp
from workbench.timer.views import signer


class TimerTest(TestCase):
    def test_timer(self):
        user = factories.UserFactory.create(is_admin=True)
        self.client.force_login(user)

        response = self.client.get("/timer/")
        self.assertContains(response, 'id="timer-state"')

        response = self.client.post("/timer/", data={"state": "[blub"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/timer/", data={"state": '{"a": 1}'})
        self.assertEqual(response.status_code, 200)

        state = TimerState.objects.get()
        self.assertEqual(state.state, {"a": 1})
        self.assertEqual(str(state), str(user))

        response = self.client.get(
            "/admin/timer/timerstate/{}/change/".format(state.id)
        )
        self.assertContains(
            response,
            '<div class="readonly"><code><pre>{&#x27;a&#x27;: 1}</pre></code></div>',
        )

    @freeze_time("2020-02-20T03:00:00+00:00")
    def test_timestamp(self):
        self.client.force_login(factories.UserFactory.create())

        response = self.client.post("/create-timestamp/", {"type": "bla"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/create-timestamp/", {"type": "start", "notes": "blub"}
        )
        self.assertEqual(response.status_code, 201)

        t = Timestamp.objects.get()
        self.assertEqual(t.type, "start")
        self.assertEqual(t.notes, "blub")
        self.assertIn(str(t), {"20.02.2020 04:00", "20.02.2020 05:00"})

    def test_timestamp_auth(self):
        response = self.client.post("/create-timestamp/", {"type": "bla"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/create-timestamp/", {"type": "start"})
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            "/create-timestamp/", {"type": "start", "user_key": "test"}
        )
        self.assertEqual(response.status_code, 403)

        user = factories.UserFactory.create()
        response = self.client.post(
            "/create-timestamp/", {"type": "start", "user_key": signer.sign(user.email)}
        )
        self.assertEqual(response.status_code, 201)

        t = Timestamp.objects.get()
        self.assertEqual(t.user, user)
