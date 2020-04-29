#  Copyright (C) 2015 Catalyst IT Ltd
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from unittest import mock

from confspirator.tests import utils as conf_utils
from django.core import mail
from rest_framework import status

from adjutant.api.models import Notification
from adjutant.tasks.models import Task
from adjutant.common.tests.fake_clients import FakeManager, setup_identity_cache
from adjutant.common.tests.utils import AdjutantAPITestCase
from adjutant.config import CONF
from adjutant import exceptions


@mock.patch("adjutant.common.user_store.IdentityManager", FakeManager)
@conf_utils.modify_conf(
    CONF,
    operations={
        "adjutant.workflow.tasks.create_project_and_user.notifications": [
            {
                "operation": "override",
                "value": {
                    "standard_handlers": ["EmailNotification"],
                    "error_handlers": ["EmailNotification"],
                    "standard_handler_config": {
                        "EmailNotification": {
                            "emails": ["example_notification@example.com"],
                            "reply": "no-reply@example.com",
                        }
                    },
                    "error_handler_config": {
                        "EmailNotification": {
                            "emails": ["example_error_notification@example.com"],
                            "reply": "no-reply@example.com",
                        }
                    },
                },
            },
        ],
    },
)
class NotificationTests(AdjutantAPITestCase):
    def test_new_project_sends_notification(self):
        """
        Confirm that the email notification handler correctly acknowledges
        notifications it sends out.

        This tests standard and error notifications.
        """
        setup_identity_cache()

        url = "/v1/openstack/sign-up"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        new_task = Task.objects.all()[0]
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].subject, "create_project_and_user notification")
        self.assertEqual(mail.outbox[1].to, ["example_notification@example.com"])

        notif = Notification.objects.all()[0]
        self.assertEqual(notif.task.uuid, new_task.uuid)
        self.assertFalse(notif.error)
        self.assertTrue(notif.acknowledged)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tasks/" + new_task.uuid
        with mock.patch(
            "adjutant.common.tests.fake_clients.FakeManager.find_project"
        ) as mocked_find:
            mocked_find.side_effect = exceptions.ServiceUnavailable(
                "Forced key error for testing."
            )
            response = self.client.post(
                url, {"approved": True}, format="json", headers=headers
            )

        # should send token email, but no new notification
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(
            mail.outbox[2].subject, "Error - create_project_and_user notification"
        )
        self.assertEqual(mail.outbox[2].to, ["example_error_notification@example.com"])

        notif = Notification.objects.all()[1]
        self.assertEqual(notif.task.uuid, new_task.uuid)
        self.assertTrue(notif.error)
        self.assertTrue(notif.acknowledged)
