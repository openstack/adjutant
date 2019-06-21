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

import mock

from django.core import mail

from rest_framework import status

from adjutant.api.models import Task, Notification
from adjutant.common.tests.fake_clients import (
    FakeManager, setup_identity_cache)
from adjutant.common.tests.utils import (
    AdjutantAPITestCase, modify_dict_settings)


@mock.patch('adjutant.common.user_store.IdentityManager',
            FakeManager)
class NotificationTests(AdjutantAPITestCase):

    @modify_dict_settings(TASK_SETTINGS={
        'key_list': ['create_project', 'notifications'],
        'operation': 'override',
        'value': {
            'EmailNotification': {
                'standard': {
                    'emails': ['example@example.com'],
                    'reply': 'no-reply@example.com',
                    'template': 'notification.txt'
                },
                'error': {
                    'emails': ['example@example.com'],
                    'reply': 'no-reply@example.com',
                    'template': 'notification.txt'
                }
            }
        }
    })
    def test_new_project_sends_notification(self):
        """
        Confirm that the email notification engine correctly acknowledges
        notifications it sends out.
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)

        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 3)

        notif = Notification.objects.all()[0]
        self.assertEqual(notif.task.uuid, new_task.uuid)
        self.assertTrue(notif.acknowledged)
