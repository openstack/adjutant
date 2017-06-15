# Copyright (C) 2017 Catalyst IT Ltd
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

from rest_framework import status

from adjutant.api.models import Token
from adjutant.api.v1.tests import (FakeManager, setup_temp_cache,
                                   AdjutantAPITestCase, modify_dict_settings)
from django.core import mail


@mock.patch('adjutant.actions.user_store.IdentityManager',
            FakeManager)
class ModifySettingsTests(AdjutantAPITestCase):
    """
    Tests designed to test the modify_dict_settings decorator.
    This is a bit weird to test because it's hard to directly test
    a lot of this stuff (especially in cases where dicts are updated rather
    than overriden).
    """

    # NOTE(amelia): Assumes the default settings for ResetUserPasswordAction
    # are that blacklisted roles are ['admin']

    def test_modify_settings_override_password(self):
        """
        Test override reset, by changing the reset password blacklisted roles
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        user2 = mock.Mock()
        user2.id = 'user_2'
        user2.name = "admin@example.com"
        user2.email = "admin@example.com"
        user2.domain = "default"
        user2.password = "admin_password"

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {user.id: ['test_role'], user2.id: ['admin']}

        setup_temp_cache({'test_project': project},
                         {user.id: user, user2.id: user2})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        admin_data = {'email': 'admin@example.com'}

        override = {
            'key_list': ['reset_password', 'action_settings',
                         'ResetUserPasswordAction', 'blacklisted_roles'],
            'operation': 'override',
            'value': ['test_role']}

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, Token.objects.count())

        # NOTE(amelia): This next bit relies on the default settings being
        # that admins can't reset their own password
        with self.modify_dict_settings(TASK_SETTINGS=override):
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(1, Token.objects.count())

            response2 = self.client.post(url, admin_data, format='json')
            self.assertEqual(response2.status_code, status.HTTP_200_OK)
            self.assertEqual(2, Token.objects.count())

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(3, Token.objects.count())

        response = self.client.post(url, admin_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(3, Token.objects.count())

    def test_modify_settings_remove_password(self):
        """
        Test override reset, by changing the reset password blacklisted roles
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "admin@example.com"
        user.email = "admin@example.com"
        user.domain = 'default'
        user.password = "test_password"

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {user.id: ['admin']}

        setup_temp_cache({'test_project': project},
                         {user.id: user})

        url = "/v1/actions/ResetPassword"
        data = {'email': 'admin@example.com'}

        override = {
            'key_list': ['reset_password', 'action_settings',
                         'ResetUserPasswordAction', 'blacklisted_roles'],
            'operation': 'remove',
            'value': ['admin']}

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(0, Token.objects.count())

        with self.modify_dict_settings(TASK_SETTINGS=override):
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(1, Token.objects.count())

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, Token.objects.count())

    @modify_dict_settings(TASK_SETTINGS={
        'key_list': ['reset_password', 'action_settings',
                     'ResetUserPasswordAction', 'blacklisted_roles'],
        'operation': 'append',
        'value': ['test_role']})
    def test_modify_settings_append_password(self):
        """
        Test override reset, by changing the reset password blacklisted roles
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        user2 = mock.Mock()
        user2.id = 'user_2'
        user2.name = "admin@example.com"
        user2.email = "admin@example.com"
        user2.domain = "default"
        user2.password = "admin_password"

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {user.id: ['test_role'], user2.id: ['admin']}

        setup_temp_cache({'test_project': project},
                         {user.id: user, user2.id: user2})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(0, Token.objects.count())

        admin_data = {'email': 'admin@example.com'}
        response2 = self.client.post(url, admin_data, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(0, Token.objects.count())

    def test_modify_settings_update_email(self):
        """
        Tests the update operator using email sending
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
        project.roles = {user.id: ['project_admin']}

        setup_temp_cache({'test_project': project},
                         {user.id: user})

        url = "/v1/actions/UpdateEmail"
        data = {'new_email': "new_test@example.com"}

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "user_id",
            'authenticated': True
        }

        override = [
            {'key_list': ['update_email', 'emails', 'token'],
             'operation': 'update',
             'value': {
                'subject': 'modified_token_email',
                'template': 'email_update_token.txt'}
             }
        ]

        response = self.client.post(url, data, headers=headers, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEquals(len(mail.outbox), 1)
        self.assertNotEquals(mail.outbox[0].subject, 'modified_token_email')

        with self.modify_dict_settings(TASK_SETTINGS=override):
            data = {'new_email': "test2@example.com"}

            response = self.client.post(url, data,
                                        headers=headers, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEquals(len(mail.outbox), 2)
            self.assertEquals(mail.outbox[1].subject, 'modified_token_email')

        data = {'new_email': "test3@example.com"}

        response = self.client.post(url, data, headers=headers, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEquals(len(mail.outbox), 3)
        self.assertNotEquals(mail.outbox[2].subject, 'modified_token_email')
