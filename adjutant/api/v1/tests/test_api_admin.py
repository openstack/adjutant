# Copyright (C) 2015 Catalyst IT Ltd
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

import json

from datetime import timedelta

from unittest import skip

from django.utils import timezone

import mock

from rest_framework import status
from rest_framework.test import APITestCase

from adjutant.api.models import Task, Token
from adjutant.api.v1.tests import (FakeManager, setup_temp_cache,
                                   modify_dict_settings)


@mock.patch('adjutant.actions.user_store.IdentityManager',
            FakeManager)
class AdminAPITests(APITestCase):
    """
    Tests to ensure the admin api endpoints work as expected within
    the context of the approval/token workflow.
    """

    def test_no_token_get(self):
        """
        Should be a 404.
        """
        url = "/v1/tokens/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {'errors': ['This token does not exist or has expired.']})

    def test_no_token_post(self):
        """
        Should be a 404.
        """
        url = "/v1/tokens/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {'errors': ['This token does not exist or has expired.']})

    def test_task_get(self):
        """
        Test the basic task detail view.
        """
        setup_temp_cache({}, {})

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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
        response = self.client.get(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_no_task_get(self):
        """
        Should be a 404.
        """
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/tasks/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.get(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'errors': ['No task with this id.']})

    def test_no_task_post(self):
        """
        Should be a 404.
        """
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/tasks/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.post(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'errors': ['No task with this id.']})

    def test_token_expired_post(self):
        """
        Expired token should do nothing, then delete itself.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        setup_temp_cache({}, {user.id: user})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['notes'],
            ['If user with email exists, reset token will be issued.'])

        new_token = Token.objects.all()[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'new_test_password'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {'errors': ['This token does not exist or has expired.']})
        self.assertEqual(0, Token.objects.count())

    def test_token_expired_get(self):
        """
        Expired token should do nothing, then delete itself.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        setup_temp_cache({}, {user.id: user})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['notes'],
            ['If user with email exists, reset token will be issued.'])

        new_token = Token.objects.all()[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()
        url = "/v1/tokens/" + new_token.token
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {'errors': ['This token does not exist or has expired.']})
        self.assertEqual(0, Token.objects.count())

    def test_task_complete(self):
        """
        Can't approve a completed task.
        """
        setup_temp_cache({}, {})

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        new_task = Task.objects.all()[0]
        new_task.completed = True
        new_task.save()
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'errors': ['This task has already been completed.']})

    def test_task_update(self):
        """
        Creates a invalid task.

        Updates it and attempts to reapprove.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {
            'project_name': "test_project2",
            'email': "test@example.com",
            'region': 'RegionOne',
        }
        response = self.client.put(url, data, format='json',
                                   headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {'notes': ['Task successfully updated.']})

        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {'notes': ['created token']})

    def test_notification_acknowledge(self):
        """
        Test that you can acknowledge a notification.
        """
        setup_temp_cache({}, {})

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_task = Task.objects.all()[0]

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        url = "/v1/notifications"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["notifications"][0]['task'],
            new_task.uuid)

        url = ("/v1/notifications/%s/" %
               response.data["notifications"][0]['uuid'])
        data = {'acknowledged': True}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.data,
                         {'notes': ['Notification acknowledged.']})

        url = "/v1/notifications"
        params = {
            "filters": json.dumps({
                "acknowledged": {"exact": False}
            })
        }
        response = self.client.get(
            url, params, format='json', headers=headers
        )
        self.assertEqual(response.data, {'notifications': []})

    def test_notification_acknowledge_list(self):
        """
        Test that you can acknowledge a list of notifications.
        """
        setup_temp_cache({}, {})

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = {'project_name': "test_project2", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        url = "/v1/notifications"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = "/v1/notifications"
        notifications = response.data["notifications"]
        data = {'notifications': [note['uuid'] for note in notifications]}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.data,
                         {'notes': ['Notifications acknowledged.']})

        url = "/v1/notifications"
        params = {
            "filters": json.dumps({
                "acknowledged": {"exact": False}
            })
        }
        response = self.client.get(
            url, params, format='json', headers=headers
        )
        self.assertEqual(response.data, {'notifications': []})

    def test_token_expired_delete(self):
        """
        test deleting of expired tokens.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        user2 = mock.Mock()
        user2.id = 'user_id2'
        user2.name = "test2@example.com"
        user2.email = "test2@example.com"
        user2.domain = 'default'
        user2.password = "test_password"

        setup_temp_cache({}, {user.id: user, user2.name: user2})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['notes'],
            ['If user with email exists, reset token will be issued.'])

        url = "/v1/actions/ResetPassword"
        data = {'email': "test2@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['notes'],
            ['If user with email exists, reset token will be issued.'])

        tokens = Token.objects.all()

        self.assertEqual(len(tokens), 2)

        new_token = tokens[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/tokens/"
        response = self.client.delete(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data,
                         {'notes': ['Deleted all expired tokens.']})
        self.assertEqual(Token.objects.count(), 1)

    def test_token_reissue(self):
        """
        test for reissue of tokens
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        setup_temp_cache({}, {user.id: user})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['notes'],
            ['If user with email exists, reset token will be issued.'])

        task = Task.objects.all()[0]
        new_token = Token.objects.all()[0]

        uuid = new_token.token

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/tokens/"
        data = {"task": task.uuid}
        response = self.client.post(url, data, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data,
                         {'notes': ['Token reissued.']})
        self.assertEqual(Token.objects.count(), 1)
        new_token = Token.objects.all()[0]
        self.assertNotEquals(new_token.token, uuid)

    def test_token_reissue_non_admin(self):
        """
        test for reissue of tokens for non-admin
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        task = Task.objects.all()[0]
        new_token = Token.objects.all()[0]

        uuid = new_token.token

        url = "/v1/tokens/"
        data = {"task": task.uuid}
        response = self.client.post(url, data, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data,
                         {'notes': ['Token reissued.']})
        self.assertEqual(Token.objects.count(), 1)
        new_token = Token.objects.all()[0]
        self.assertNotEquals(new_token.token, uuid)

        # Now confirm it is limited by project id properly.
        headers['project_id'] = "test_project_id2"
        response = self.client.post(url, data, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data,
                         {'errors': ['No task with this id.']})

    def test_cancel_task(self):
        """
        Ensure the ability to cancel a task.
        """

        setup_temp_cache({}, {})

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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
        response = self.client.delete(url, format='json',
                                      headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.put(url, format='json',
                                   headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_task_sent_token(self):
        """
        Ensure the ability to cancel a task after the token is sent.
        """

        setup_temp_cache({}, {})

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(url, format='json',
                                      headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_task_update_unapprove(self):
        """
        Ensure task update doesn't work for approved actions.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({}, {})

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_task = Task.objects.all()[0]
        self.assertEqual(new_task.approved, True)

        data = {'project_name': "test_project2", 'email': "test2@example.com"}
        response = self.client.put(url, data, format='json',
                                   headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_task_own(self):
        """
        Ensure the ability to cancel your own task.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.delete(url, format='json',
                                      headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers['roles'] = "admin"
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.put(url, format='json',
                                   headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_task_own_fail(self):
        """
        Ensure the ability to cancel ONLY your own task.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        headers['project_id'] = "fake_project_id"
        response = self.client.delete(url, format='json',
                                      headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_task_list(self):
        """
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = {'email': "test2@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = {'email': "test3@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/tasks"
        response = self.client.get(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['tasks']), 3)

    def test_task_list_ordering(self):
        """
        Test that tasks returns in the default sort.
        The default sort is by created_on descending.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = {'email': "test2@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = {'email': "test3@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/tasks"
        response = self.client.get(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sorted_list = sorted(
            response.data['tasks'],
            key=lambda k: k['created_on'],
            reverse=True)

        for i, task in enumerate(sorted_list):
            self.assertEqual(task, response.data['tasks'][i])

    def test_task_list_filter(self):
        """
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = {'email': "test2@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project2", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        params = {
            "filters": json.dumps({
                "task_type": {"exact": "create_project"}
            })
        }

        url = "/v1/tasks"
        response = self.client.get(
            url, params, format='json', headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['tasks']), 1)

        params = {
            "filters": json.dumps({
                "task_type": {"exact": "invite_user"}
            })
        }
        response = self.client.get(
            url, params, format='json', headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['tasks']), 2)

    # TODO(adriant): enable this test again when filters are properly
    # blacklisted.
    @skip("Does not apply yet.")
    def test_task_list_filter_cross_project(self):
        """
        Ensure you can't override the initial project_id filter if
        you are not admin.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        project2 = mock.Mock()
        project2.id = 'test_project_id_2'
        project2.name = 'test_project_2'
        project2.domain = 'default'
        project2.roles = {}

        setup_temp_cache(
            {'test_project': project, 'test_project_2': project2}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "owner@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id_2",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        params = {
            "filters": json.dumps({
                "project_id": {"exact": "test_project_id"},
                "task_type": {"exact": "invite_user"}
            })
        }
        url = "/v1/tasks"
        response = self.client.get(
            url, params, format='json', headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['tasks']), 0)

    def test_task_list_filter_formating(self):
        """
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        # not proper json
        params = {
            "filters": {
                "task_type": {"exact": "create_project"}
            }
        }
        url = "/v1/tasks"
        response = self.client.get(
            url, params, format='json', headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # inncorrect format
        params = {
            "filters": json.dumps("gibbberish")
        }
        response = self.client.get(
            url, params, format='json', headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # inncorrect format
        params = {
            "filters": json.dumps({
                "task_type": ["exact", "value"]
            })
        }
        response = self.client.get(
            url, params, format='json', headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # invalid operation
        params = {
            "filters": json.dumps({
                "task_type": {"dont_find": "value"}
            })
        }
        response = self.client.get(
            url, params, format='json', headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # invalid field
        params = {
            "filters": json.dumps({
                "fake": {"exact": "value"}
            })
        }
        response = self.client.get(
            url, params, format='json', headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @modify_dict_settings(TASK_SETTINGS={
        'key_list': ['reset_password', 'action_settings',
                     'ResetUserPasswordAction', 'blacklisted_roles'],
        'operation': 'append',
        'value': ['admin']
    })
    def test_reset_admin(self):
        """
        Ensure that you cannot issue a password reset for an
        admin user.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {user.id: ['admin']}

        setup_temp_cache({'test_project': project}, {user.id: user})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['notes'],
            ['If user with email exists, reset token will be issued.'])
        self.assertEqual(0, Token.objects.count())
