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

from datetime import timedelta
from unittest import mock

from confspirator.tests import utils as conf_utils
from django.utils import timezone
from rest_framework import status

from adjutant.api.models import Token, Task
from adjutant.common.tests import fake_clients
from adjutant.common.tests.fake_clients import (
    FakeManager,
    setup_identity_cache,
    get_fake_neutron,
    get_fake_novaclient,
    get_fake_cinderclient,
    get_fake_octaviaclient,
    get_fake_troveclient,
    cinder_cache,
    nova_cache,
    neutron_cache,
    octavia_cache,
    trove_cache,
    setup_mock_caches,
    setup_quota_cache,
    FakeResource,
)
from adjutant.common.tests.utils import AdjutantAPITestCase
from adjutant.config import CONF


@mock.patch("adjutant.common.user_store.IdentityManager", FakeManager)
class OpenstackAPITests(AdjutantAPITestCase):
    """
    DelegateAPI tests specific to the openstack style urls.
    Many of the original DelegateAPI tests are valid and need
    not be repeated here, but some additional features in the
    unique DelegateAPI need testing.
    """

    def test_new_user(self):
        """
        Ensure the new user workflow goes as expected.
        Create task, create token, submit token.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/openstack/users"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {"password": "testpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_list(self):
        """
        Test that a non-admin user can list users.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/openstack/users"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {"password": "testpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = "/v1/openstack/users"
        data = {
            "email": "test2@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["users"]), 2)
        self.assertTrue(b"test2@example.com" in response.content)

    def test_user_list_inherited(self):
        """
        Test that user list returns inherited roles correctly.
        """
        project = fake_clients.FakeProject(name="test_project")
        project2 = fake_clients.FakeProject(
            name="test_project/child", parent_id=project.id
        )
        project3 = fake_clients.FakeProject(
            name="test_project/child/another", parent_id=project2.id
        )

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        user2 = fake_clients.FakeUser(
            name="test2@example.com", password="123", email="test2@example.com"
        )

        user3 = fake_clients.FakeUser(
            name="test3@example.com", password="123", email="test2@example.com"
        )

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_admin",
                user={"id": user.id},
                inherited=True,
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project2.id}},
                role_name="project_mod",
                user={"id": user2.id},
                inherited=True,
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project3.id}},
                role_name="member",
                user={"id": user3.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project3.id}},
                role_name="member",
                user={"id": user3.id},
                inherited=True,
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project3.id}},
                role_name="project_mod",
                user={"id": user3.id},
            ),
        ]

        setup_identity_cache(
            projects=[project, project2, project3],
            users=[user, user2, user3],
            role_assignments=assignments,
        )

        url = "/v1/openstack/users"
        headers = {
            "project_name": "test_project",
            "project_id": project3.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        response = self.client.get(url, headers=headers)
        response_json = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project_users = []
        inherited_users = []
        for u in response_json["users"]:
            if u["cohort"] == "Inherited":
                inherited_users.append(u)
            else:
                project_users.append(u)
        self.assertEqual(len(inherited_users), 2)
        self.assertEqual(len(project_users), 1)

        for u in inherited_users:
            if u["id"] == user.id:
                self.assertEqual(u["roles"], ["project_admin"])
            if u["id"] == user2.id:
                self.assertEqual(u["roles"], ["project_mod"])

        normal_user = project_users[0]
        self.assertEqual(normal_user["roles"], ["member", "project_mod"])
        self.assertEqual(normal_user["inherited_roles"], ["member"])

    def test_user_detail(self):
        """
        Confirm that the user detail view functions as expected
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user.id},
                inherited=True,
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user.id},
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=assignments
        )

        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/users/%s" % user.id
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["username"], "test@example.com")
        self.assertEqual(response.json()["roles"], ["member"])
        self.assertEqual(response.json()["inherited_roles"], ["member"])

    def test_user_list_manageable(self):
        """
        Confirm that the manageable value is set correctly.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        user2 = fake_clients.FakeUser(
            name="test2@example.com", password="123", email="test2@example.com"
        )

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_admin",
                user={"id": user.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user2.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_mod",
                user={"id": user2.id},
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user, user2], role_assignments=assignments
        )

        url = "/v1/openstack/users"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/users"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["users"]), 2)

        for adj_user in response.json()["users"]:
            if adj_user["id"] == user.id:
                self.assertFalse(adj_user["manageable"])
            if adj_user["id"] == user2.id:
                self.assertTrue(adj_user["manageable"])

    def test_remove_user_role(self):
        """Remove all roles on a user from our project"""
        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignment = fake_clients.FakeRoleAssignment(
            scope={"project": {"id": project.id}},
            role_name="member",
            user={"id": user.id},
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment]
        )

        admin_headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        # admins removes role from the test user
        url = "/v1/openstack/users/%s/roles" % user.id
        data = {"roles": ["member"]}
        response = self.client.delete(url, data, format="json", headers=admin_headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_new_user_username_not_email(self):
        """
        Ensure the new user workflow goes as expected.
        Create task, create token, submit token.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/openstack/users"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
            "username": "user_name",
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {"password": "testpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@mock.patch("adjutant.common.user_store.IdentityManager", FakeManager)
@mock.patch("adjutant.common.openstack_clients.get_novaclient", get_fake_novaclient)
@mock.patch("adjutant.common.openstack_clients.get_neutronclient", get_fake_neutron)
@mock.patch("adjutant.common.openstack_clients.get_cinderclient", get_fake_cinderclient)
@mock.patch(
    "adjutant.common.openstack_clients.get_octaviaclient", get_fake_octaviaclient
)
@mock.patch("adjutant.common.openstack_clients.get_troveclient", get_fake_troveclient)
class QuotaAPITests(AdjutantAPITestCase):
    def setUp(self):
        super(QuotaAPITests, self).setUp()
        setup_mock_caches("RegionOne", "test_project_id")
        setup_mock_caches("RegionTwo", "test_project_id")

    def check_quota_cache(self, region_name, project_id, size, extra_services=None):
        """
        Helper function to check if the global quota caches now match the size
        defined in the config
        """
        if extra_services is None:
            extra_services = []

        cinderquota = cinder_cache[region_name][project_id]["quota"]
        gigabytes = CONF.quota.sizes[size]["cinder"]["gigabytes"]
        self.assertEqual(cinderquota["gigabytes"], gigabytes)

        novaquota = nova_cache[region_name][project_id]["quota"]
        ram = CONF.quota.sizes[size]["nova"]["ram"]
        self.assertEqual(novaquota["ram"], ram)

        neutronquota = neutron_cache[region_name][project_id]["quota"]
        network = CONF.quota.sizes[size]["neutron"]["network"]
        self.assertEqual(neutronquota["network"], network)

        if "octavia" in extra_services:
            octaviaquota = octavia_cache[region_name][project_id]["quota"]
            load_balancer = CONF.quota.sizes.get(size)["octavia"]["load_balancer"]
            self.assertEqual(octaviaquota["load_balancer"], load_balancer)

        if "trove" in extra_services:
            trove_quota = trove_cache[region_name][project_id]["quota"]
            instance = CONF.quota.sizes.get(size)["trove"]["instances"]
            self.assertEqual(trove_quota["instances"], instance)

    def test_update_quota_no_history(self):
        """Update the quota size of a project with no history"""

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        admin_headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "medium", "regions": ["RegionOne"]}

        response = self.client.post(url, data, headers=admin_headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have changed
        self.check_quota_cache("RegionOne", project.id, "medium")

    def test_update_quota_history(self):
        """
        Update the quota size of a project with a quota change recently
        It should update the quota the first time but wait for admin approval
        the second time
        """
        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        admin_headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "medium", "regions": ["RegionOne"]}
        response = self.client.post(url, data, headers=admin_headers, format="json")
        # First check we can actually access the page correctly
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have changed
        self.check_quota_cache("RegionOne", project.id, "medium")

        data = {"size": "large", "regions": ["RegionOne"]}
        response = self.client.post(url, data, headers=admin_headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have not changed
        self.check_quota_cache("RegionOne", project.id, "medium")

        # Approve the quota change as admin
        headers = {
            "project_name": "admin_project",
            "project_id": project.id,
            "roles": "admin,member",
            "username": "admin",
            "user_id": "admin_id",
            "authenticated": True,
        }

        # Grab the details for the second task and approve it
        new_task = Task.objects.all()[1]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"notes": ["Task completed successfully."]})

        # Quotas should have changed to large
        self.check_quota_cache("RegionOne", project.id, "large")

    def test_update_quota_history_smaller(self):
        """
        Update quota to a smaller quota right after a change to a larger
        quota. Should auto approve to smaller quotas regardless of history.
        """
        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        admin_headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "medium", "regions": ["RegionOne"]}
        response = self.client.post(url, data, headers=admin_headers, format="json")
        # First check we can actually access the page correctly
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have changed
        self.check_quota_cache("RegionOne", project.id, "medium")

        data = {"size": "small", "regions": ["RegionOne"]}
        response = self.client.post(url, data, headers=admin_headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have changed
        self.check_quota_cache("RegionOne", project.id, "small")

    def test_update_quota_old_history(self):
        """
        Update the quota size of a project with a quota change 31 days ago
        It should update the quota the first time without approval
        """

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        admin_headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "medium", "regions": ["RegionOne"]}
        response = self.client.post(url, data, headers=admin_headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have changed
        self.check_quota_cache("RegionOne", project.id, "medium")

        # Fudge the data to make the task occur 31 days ago
        task = Task.objects.all()[0]
        task.completed_on = timezone.now() - timedelta(days=32)
        task.save()

        data = {"size": "small", "regions": ["RegionOne"]}
        response = self.client.post(url, data, headers=admin_headers, format="json")
        # First check we can actually access the page correctly
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have changed
        self.check_quota_cache("RegionOne", project.id, "small")

    def test_update_quota_other_project_history(self):
        """
        Tests that a quota update to another project does not interfer
        with the 30 days per project limit.
        """

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        project2 = fake_clients.FakeProject(name="second_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project, project2], users=[user])

        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        setup_mock_caches("RegionOne", project2.id)

        url = "/v1/openstack/quotas/"

        data = {"size": "medium", "regions": ["RegionOne"]}
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have changed
        self.check_quota_cache("RegionOne", project.id, "medium")
        headers = {
            "project_name": "second_project",
            "project_id": project2.id,
            "roles": "project_admin,member,project_mod",
            "username": "test2@example.com",
            "user_id": user.id,
            "authenticated": True,
        }

        data = {"regions": ["RegionOne"], "size": "medium", "project_id": project2.id}
        response = self.client.post(url, data, headers=headers, format="json")
        # First check we can actually access the page correctly
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have changed
        self.check_quota_cache("RegionOne", project2.id, "medium")

    def test_update_quota_outside_range(self):
        """
        Attempts to update the quota size to a value outside of the
        project's pre-approved range.
        """

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        admin_headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "large", "regions": ["RegionOne"]}
        response = self.client.post(url, data, headers=admin_headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have not changed (stayed small)
        self.check_quota_cache("RegionOne", project.id, "small")

        # Approve and test for change

        # Approve the quota change as admin
        headers = {
            "project_name": "admin_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "admin",
            "user_id": "admin_id",
            "authenticated": True,
        }

        # Grab the details for the task and approve it
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"notes": ["Task completed successfully."]})

        self.check_quota_cache("RegionOne", project.id, "large")

    def test_calculate_custom_quota_size(self):
        """
        Calculates the best 'fit' quota size from a custom quota.
        """

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        admin_headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": user.id,
            "authenticated": True,
        }

        cinderquota = cinder_cache["RegionOne"]["test_project_id"]["quota"]
        cinderquota["gigabytes"] = 6000
        novaquota = nova_cache["RegionOne"]["test_project_id"]["quota"]
        novaquota["ram"] = 70000
        neutronquota = neutron_cache["RegionOne"]["test_project_id"]["quota"]
        neutronquota["network"] = 4

        url = "/v1/openstack/quotas/?regions=RegionOne"

        response = self.client.get(url, headers=admin_headers)
        # First check we can actually access the page correctly
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["regions"][0]["current_quota_size"], "small")

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.quota.sizes": [
                {
                    "operation": "update",
                    "value": {
                        "zero": {
                            "nova": {
                                "instances": 0,
                                "cores": 0,
                                "ram": 0,
                                "floating_ips": 0,
                                "fixed_ips": 0,
                                "metadata_items": 0,
                                "injected_files": 0,
                                "injected_file_content_bytes": 0,
                                "key_pairs": 50,
                                "security_groups": 0,
                                "security_group_rules": 0,
                            },
                            "cinder": {
                                "gigabytes": 0,
                                "snapshots": 0,
                                "volumes": 0,
                            },
                            "neutron": {
                                "floatingip": 0,
                                "network": 0,
                                "port": 0,
                                "router": 0,
                                "security_group": 0,
                                "security_group_rule": 0,
                            },
                        }
                    },
                },
            ],
            "adjutant.quota.sizes_ascending": [
                {"operation": "prepend", "value": "zero"},
            ],
        },
    )
    def test_calculate_quota_size_zero(self):
        """
        Ensures that a zero quota enabled picks up
        """

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        admin_headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        setup_quota_cache("RegionOne", project.id, "small")

        url = "/v1/openstack/quotas/?regions=RegionOne"

        response = self.client.get(url, headers=admin_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["regions"][0]["current_quota_size"], "small")

        cinderquota = cinder_cache["RegionOne"][project.id]["quota"]
        cinderquota["gigabytes"] = 0

        # Check that the zero value doesn't interfer with being small
        response = self.client.get(url, headers=admin_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["regions"][0]["current_quota_size"], "small")

        setup_quota_cache("RegionOne", project.id, "zero")

        url = "/v1/openstack/quotas/?regions=RegionOne"

        response = self.client.get(url, headers=admin_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["regions"][0]["current_quota_size"], "zero")

        # Check that the zero quota will still be counted even if
        # one value is not zero
        cinderquota = cinder_cache["RegionOne"][project.id]["quota"]
        cinderquota["gigabytes"] = 600

        response = self.client.get(url, headers=admin_headers)
        # First check we can actually access the page correctly
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["regions"][0]["current_quota_size"], "zero")

    def test_return_quota_history(self):
        """
        Ensures that the correct quota history and usage data is returned
        """

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "large", "regions": ["RegionOne", "RegionTwo"]}
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        response = self.client.get(url, headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        recent_task = response.data["active_quota_tasks"][0]
        self.assertEqual(recent_task["size"], "large")
        self.assertEqual(recent_task["request_user"], "test@example.com")
        self.assertEqual(recent_task["status"], "Awaiting Approval")

    def test_set_multi_region_quota(self):
        """Sets a quota to all to all regions in a project"""

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "medium", "regions": ["RegionOne", "RegionTwo"]}
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        self.check_quota_cache("RegionOne", "test_project_id", "medium")

        self.check_quota_cache("RegionTwo", "test_project_id", "medium")

    def test_set_multi_region_quota_history(self):
        """
        Attempts to set a multi region quota with a multi region update history
        """

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "medium", "regions": ["RegionOne", "RegionTwo"]}
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        self.check_quota_cache("RegionOne", project.id, "medium")

        self.check_quota_cache("RegionTwo", project.id, "medium")

        data = {"size": "large"}
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # All of them stay the same
        self.check_quota_cache("RegionOne", project.id, "medium")

        self.check_quota_cache("RegionTwo", project.id, "medium")

        # Approve the task
        headers = {
            "project_name": "admin_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "admin",
            "user_id": "admin_id",
            "authenticated": True,
        }

        new_task = Task.objects.all()[1]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"notes": ["Task completed successfully."]})

        self.check_quota_cache("RegionOne", project.id, "large")

        self.check_quota_cache("RegionTwo", project.id, "large")

    def test_set_multi_quota_single_history(self):
        """
        Attempts to set a multi region quota with a single region quota
        update history
        """

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        # Setup custom parts of the quota still within 'small' however

        url = "/v1/openstack/quotas/"

        data = {"size": "medium", "regions": ["RegionOne"]}
        response = self.client.post(url, data, headers=headers, format="json")
        # First check we can actually access the page correctly
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        self.check_quota_cache("RegionOne", project.id, "medium")

        url = "/v1/openstack/quotas/"

        data = {"size": "small", "regions": ["RegionOne", "RegionTwo"]}
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Quotas stay the same
        self.check_quota_cache("RegionOne", project.id, "medium")
        self.check_quota_cache("RegionTwo", project.id, "small")

        headers = {
            "project_name": "admin_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "admin",
            "user_id": "admin_id",
            "authenticated": True,
        }

        new_task = Task.objects.all()[1]
        url = "/v1/tasks/" + new_task.uuid

        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"notes": ["Task completed successfully."]})

        self.check_quota_cache("RegionOne", project.id, "small")
        self.check_quota_cache("RegionTwo", project.id, "small")

    def test_set_quota_over_limit(self):
        """Attempts to set a smaller quota than the current usage"""
        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        setup_quota_cache("RegionOne", project.id, "medium")
        # Setup current quota as medium
        # Create a number of lists with limits higher than the small quota

        global nova_cache
        nova_cache["RegionOne"][project.id]["absolute"]["totalInstancesUsed"] = 11

        url = "/v1/openstack/quotas/"

        data = {"size": "small", "regions": ["RegionOne"]}
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.check_quota_cache("RegionOne", project.id, "medium")

        data = {"size": "small", "regions": ["RegionOne"]}

        nova_cache["RegionOne"][project.id]["absolute"]["totalInstancesUsed"] = 10

        # Test for cinder resources
        volume_list = [FakeResource(10) for i in range(21)]
        cinder_cache["RegionOne"][project.id]["volumes"] = volume_list

        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.check_quota_cache("RegionOne", project.id, "medium")

        # Test for neutron resources
        cinder_cache["RegionOne"][project.id]["volumes"] = []
        net_list = [{} for i in range(4)]
        neutron_cache["RegionOne"][project.id]["networks"] = net_list
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.check_quota_cache("RegionOne", project.id, "medium")

        # Check that after they are all cleared to sub small levels
        # the quota updates
        neutron_cache["RegionOne"][project.id]["networks"] = []
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        self.check_quota_cache("RegionOne", project.id, "small")

    def test_set_quota_invalid_region(self):
        """Attempts to set a quota on a non-existent region"""
        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "small", "regions": ["RegionThree"]}
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.tasks.update_quota.allow_auto_approve": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_no_auto_approved_quota_change(self):
        """Test allow_auto_approve config setting on a task."""

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "medium", "regions": ["RegionOne", "RegionTwo"]}
        response = self.client.post(url, data, headers=headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        self.check_quota_cache("RegionOne", "test_project_id", "small")

        self.check_quota_cache("RegionTwo", "test_project_id", "small")

    def test_view_correct_sizes(self):
        """
        Calculates the best 'fit' quota size from a custom quota.
        """

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        admin_headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": user.id,
            "authenticated": True,
        }
        url = "/v1/openstack/quotas/?regions=RegionOne"

        response = self.client.get(url, headers=admin_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["regions"][0]["current_quota_size"], "small")
        self.assertEqual(
            response.data["regions"][0]["quota_change_options"], ["medium"]
        )

        cinder_cache["RegionOne"][project.id]["quota"] = CONF.quota.sizes["large"][
            "cinder"
        ]

        nova_cache["RegionOne"][project.id]["quota"] = CONF.quota.sizes["large"]["nova"]

        neutron_cache["RegionOne"][project.id]["quota"] = CONF.quota.sizes["large"][
            "neutron"
        ]

        response = self.client.get(url, headers=admin_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["regions"][0]["current_quota_size"], "large")
        self.assertEqual(
            response.data["regions"][0]["quota_change_options"], ["small", "medium"]
        )

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.quota.services": [
                {
                    "operation": "override",
                    "value": {"*": ["cinder", "neutron", "nova", "octavia", "trove"]},
                },
            ],
        },
    )
    def test_update_quota_extra_services(self):
        """Update quota for extra services"""

        project = fake_clients.FakeProject(name="test_project", id="test_project_id")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        admin_headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "user_id",
            "authenticated": True,
        }

        url = "/v1/openstack/quotas/"

        data = {"size": "medium", "regions": ["RegionOne"]}

        response = self.client.post(url, data, headers=admin_headers, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Then check to see the quotas have changed
        self.check_quota_cache(
            "RegionOne", project.id, "medium", extra_services=["octavia", "trove"]
        )
