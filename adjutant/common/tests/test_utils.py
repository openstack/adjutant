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
from adjutant.common.tests import fake_clients
from adjutant.common.tests.fake_clients import (
    FakeManager, setup_identity_cache)
from adjutant.common.tests.utils import (AdjutantAPITestCase,
                                         modify_dict_settings)

from django.core import mail


@mock.patch('adjutant.common.user_store.IdentityManager',
            FakeManager)
class ModifySettingsTests(AdjutantAPITestCase):
    """
    Tests designed to test the modify_dict_settings decorator.
    This is a bit weird to test because it's hard to directly test
    a lot of this stuff (especially in cases where dicts are updated rather
    than overridden).
    """

    # NOTE(amelia): Assumes the default settings for ResetUserPasswordAction
    # are that blacklisted roles are ['admin']

    def test_modify_settings_override_password(self):
        """
        Test override reset, by changing the reset password blacklisted roles
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="test_password",
            email="test@example.com")

        user2 = fake_clients.FakeUser(
            name="admin@example.com", password="admin_password",
            email="admin@example.com")

        project = fake_clients.FakeProject(name="test_project")

        test_role = fake_clients.FakeRole("test_role")

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="test_role",
                user={'id': user.id}
            ),
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="admin",
                user={'id': user2.id}
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user, user2],
            role_assignments=assignments, extra_roles=[test_role])

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

        user = fake_clients.FakeUser(
            name="admin@example.com", password="admin_password",
            email="admin@example.com")

        project = fake_clients.FakeProject(name="test_project")

        assignment = fake_clients.FakeRoleAssignment(
            scope={'project': {'id': project.id}},
            role_name="admin",
            user={'id': user.id}
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment])

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

        user = fake_clients.FakeUser(
            name="test@example.com", password="test_password",
            email="test@example.com")

        user2 = fake_clients.FakeUser(
            name="admin@example.com", password="admin_password",
            email="admin@example.com")

        project = fake_clients.FakeProject(name="test_project")

        test_role = fake_clients.FakeRole("test_role")

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="test_role",
                user={'id': user.id}
            ),
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="admin",
                user={'id': user2.id}
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user, user2],
            role_assignments=assignments, extra_roles=[test_role])

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

        user = fake_clients.FakeUser(
            name="test@example.com", password="test_password",
            email="test@example.com")

        project = fake_clients.FakeProject(name="test_project")

        assignment = fake_clients.FakeRoleAssignment(
            scope={'project': {'id': project.id}},
            role_name="project_admin",
            user={'id': user.id}
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment])

        url = "/v1/actions/UpdateEmail"
        data = {'new_email': "new_test@example.com"}

        headers = {
            'project_name': "test_project",
            'project_id': project.id,
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': user.id,
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
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotEqual(mail.outbox[0].subject, 'modified_token_email')

        with self.modify_dict_settings(TASK_SETTINGS=override):
            data = {'new_email': "test2@example.com"}

            response = self.client.post(url, data,
                                        headers=headers, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(mail.outbox), 2)
            self.assertEqual(mail.outbox[1].subject, 'modified_token_email')

        data = {'new_email': "test3@example.com"}

        response = self.client.post(url, data, headers=headers, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(mail.outbox), 3)
        self.assertNotEqual(mail.outbox[2].subject, 'modified_token_email')
