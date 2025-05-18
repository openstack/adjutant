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

from unittest import mock

from confspirator.tests import utils as conf_utils

from adjutant.actions.v1.resources import (
    NewDefaultNetworkAction,
    NewProjectDefaultNetworkAction,
    SetProjectQuotaAction,
    UpdateProjectQuotasAction,
)
from adjutant.api.models import Task
from adjutant.common.tests.fake_clients import (
    FakeProject,
    FakeUser,
    FakeManager,
    setup_identity_cache,
    get_fake_neutron,
    get_fake_novaclient,
    get_fake_cinderclient,
    get_fake_troveclient,
    setup_neutron_cache,
    neutron_cache,
    cinder_cache,
    nova_cache,
    setup_mock_caches,
    get_fake_octaviaclient,
    octavia_cache,
    trove_cache,
)
from adjutant.common.tests.utils import AdjutantTestCase
from adjutant.config import CONF


@mock.patch("adjutant.common.user_store.IdentityManager", FakeManager)
@mock.patch(
    "adjutant.actions.v1.resources.openstack_clients.get_neutronclient",
    get_fake_neutron,
)
@mock.patch("adjutant.common.openstack_clients.get_neutronclient", get_fake_neutron)
@mock.patch("adjutant.common.openstack_clients.get_novaclient", get_fake_novaclient)
@mock.patch("adjutant.common.openstack_clients.get_cinderclient", get_fake_cinderclient)
@conf_utils.modify_conf(
    CONF,
    operations={
        "adjutant.workflow.action_defaults.NewDefaultNetworkAction.regions": [
            {
                "operation": "override",
                "value": {
                    "RegionOne": {
                        "dns_nameservers": ["193.168.1.2", "193.168.1.3"],
                        "subnet_cidr": "192.168.1.0/24",
                        "network_name": "somenetwork",
                        "public_network": "3cb50f61-5bce-4c03-96e6-8e262e12bb35",
                        "router_name": "somerouter",
                        "subnet_name": "somesubnet",
                    }
                },
            }
        ],
        "adjutant.quota.sizes": [
            {
                "operation": "update",
                "value": {
                    "large_cinder_only": {
                        "cinder": {"gigabytes": 50001, "volumes": 200, "snapshots": 600}
                    }
                },
            }
        ],
        "adjutant.workflow.action_defaults.SetProjectQuotaAction.region_sizes": [
            {
                "operation": "override",
                "value": {"RegionOne": "small", "RegionThree": "large_cinder_only"},
            },
        ],
    },
)
class ProjectSetupActionTests(AdjutantTestCase):
    def test_network_setup(self):
        """
        Base case, setup a new network , no issues.
        """
        setup_neutron_cache("RegionOne", "test_project_id")
        task = Task.objects.create(
            keystone_user={"roles": ["admin"], "project_id": "test_project_id"}
        )

        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        setup_identity_cache(projects=[project])

        data = {
            "setup_network": True,
            "region": "RegionOne",
            "project_id": "test_project_id",
        }

        action = NewDefaultNetworkAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(
            action.action.cache,
            {
                "network_id_RegionOne": "net_id_0",
                "port_id_RegionOne": "port_id_3",
                "router_id_RegionOne": "router_id_2",
                "subnet_id_RegionOne": "subnet_id_1",
            },
        )

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 1
        )

    def test_network_setup_old_cache_compatibility(self):
        """
        Check that a task with old-tyle cache values defined is compatible
        with the new implementation.
        """
        setup_neutron_cache("RegionOne", "test_project_id")

        task = Task.objects.create(
            keystone_user={"roles": ["admin"], "project_id": "test_project_id"}
        )

        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        setup_identity_cache(projects=[project])

        data = {
            "setup_network": True,
            "region": "RegionOne",
            "project_id": "test_project_id",
        }

        action = NewDefaultNetworkAction(data, task=task, order=1)

        neutron_cache[data["region"]][project.id]["networks"]["net_id_0"] = {
            "name": "somenetwork",
            "tenant_id": project.id,
            "admin_state_up": True,
        }
        neutron_cache[data["region"]][project.id]["subnets"]["subnet_id_1"] = {
            "network_id": "net_id_0",
            "ip_version": 4,
            "tenant_id": project.id,
            "dns_nameservers": ["193.168.1.2", "193.168.1.3"],
            "cidr": "192.168.1.0/24",
        }
        neutron_cache[data["region"]][project.id]["routers"]["router_id_2"] = {
            "name": "somerouter",
            "external_gateway_info": {
                "network_id": "3cb50f61-5bce-4c03-96e6-8e262e12bb35",
            },
            "tenant_id": project.id,
            "admin_state_up": True,
        }
        neutron_cache[data["region"]]["i"] = 4
        action.action.cache = {
            "network_id": "net_id_0",
            "port_id": "port_id_3",
            "router_id": "router_id_2",
            "subnet_id": "subnet_id_1",
        }

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(
            action.action.cache,
            {
                "network_id": "net_id_0",
                "port_id": "port_id_3",
                "router_id": "router_id_2",
                "subnet_id": "subnet_id_1",
                "network_id_RegionOne": "net_id_0",
                "port_id_RegionOne": "port_id_3",
                "router_id_RegionOne": "router_id_2",
                "subnet_id_RegionOne": "subnet_id_1",
            },
        )

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 1
        )

    def test_network_setup_no_setup(self):
        """
        Told not to setup, should do nothing.
        """
        setup_neutron_cache("RegionOne", "test_project_id")
        task = Task.objects.create(
            keystone_user={"roles": ["admin"], "project_id": "test_project_id"}
        )

        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        setup_identity_cache(projects=[project])

        data = {
            "setup_network": False,
            "region": "RegionOne",
            "project_id": "test_project_id",
        }

        action = NewDefaultNetworkAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(action.action.cache, {})

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 0
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 0
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 0
        )

    @conf_utils.modify_conf(
        CONF,
        operations={
            (
                "adjutant.workflow.action_defaults.NewDefaultNetworkAction"
                ".create_in_regions"
            ): [
                {"operation": "override", "value": ["RegionOne", "RegionTwo"]},
            ],
        },
    )
    def test_network_setup_create_in_regions(self):
        """
        Check that all regions specified in 'create_in_regions'
        have a default network created.
        """
        setup_neutron_cache("RegionOne", "test_project_id")
        setup_neutron_cache("RegionTwo", "test_project_id")

        task = Task.objects.create(
            keystone_user={"roles": ["admin"], "project_id": "test_project_id"}
        )

        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        setup_identity_cache(projects=[project])

        data = {
            "setup_network": True,
            "region": "RegionOne",
            "project_id": "test_project_id",
        }

        action = NewDefaultNetworkAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(
            action.action.cache,
            {
                "network_id_RegionOne": "net_id_0",
                "port_id_RegionOne": "port_id_3",
                "router_id_RegionOne": "router_id_2",
                "subnet_id_RegionOne": "subnet_id_1",
                "network_id_RegionTwo": "net_id_0",
                "port_id_RegionTwo": "port_id_3",
                "router_id_RegionTwo": "router_id_2",
                "subnet_id_RegionTwo": "subnet_id_1",
            },
        )

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionTwo"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionTwo"]["test_project_id"]["routers"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionTwo"]["test_project_id"]["subnets"]), 1
        )

    @conf_utils.modify_conf(
        CONF,
        operations={
            (
                "adjutant.workflow.action_defaults.NewDefaultNetworkAction"
                ".create_in_all_regions"
            ): [
                {"operation": "override", "value": True},
            ],
        },
    )
    def test_network_setup_create_in_all_regions(self):
        """
        Check that all regions have a default network created
        when 'create_in_all_regions' is set to True.
        """
        setup_neutron_cache("RegionOne", "test_project_id")
        setup_neutron_cache("RegionTwo", "test_project_id")

        task = Task.objects.create(
            keystone_user={"roles": ["admin"], "project_id": "test_project_id"}
        )

        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        setup_identity_cache(projects=[project])

        data = {
            "setup_network": True,
            "region": "RegionOne",
            "project_id": "test_project_id",
        }

        action = NewDefaultNetworkAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(
            action.action.cache,
            {
                "network_id_RegionOne": "net_id_0",
                "port_id_RegionOne": "port_id_3",
                "router_id_RegionOne": "router_id_2",
                "subnet_id_RegionOne": "subnet_id_1",
                "network_id_RegionTwo": "net_id_0",
                "port_id_RegionTwo": "port_id_3",
                "router_id_RegionTwo": "router_id_2",
                "subnet_id_RegionTwo": "subnet_id_1",
            },
        )

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionTwo"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionTwo"]["test_project_id"]["routers"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionTwo"]["test_project_id"]["subnets"]), 1
        )

    def test_network_setup_fail(self):
        """
        Should fail, but on re_approve will continue where it left off.
        """
        setup_neutron_cache("RegionOne", "test_project_id")
        task = Task.objects.create(
            keystone_user={"roles": ["admin"], "project_id": "test_project_id"}
        )

        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        setup_identity_cache(projects=[project])

        data = {
            "setup_network": True,
            "region": "RegionOne",
            "project_id": "test_project_id",
        }

        action = NewDefaultNetworkAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        neutron_cache["RegionOne"]["test_project_id"]["routers"] = []

        try:
            action.approve()
            self.fail("Shouldn't get here.")
        except Exception:
            pass

        self.assertEqual(
            action.action.cache,
            {
                "network_id_RegionOne": "net_id_0",
                "subnet_id_RegionOne": "subnet_id_1",
            },
        )

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 0
        )

        neutron_cache["RegionOne"]["test_project_id"]["routers"] = {}

        action.approve()

        self.assertEqual(
            action.action.cache,
            {
                "network_id_RegionOne": "net_id_0",
                "port_id_RegionOne": "port_id_3",
                "router_id_RegionOne": "router_id_2",
                "subnet_id_RegionOne": "subnet_id_1",
            },
        )

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 1
        )

    def test_new_project_network_setup(self):
        """
        Base case, setup network after a new project, no issues.
        """
        setup_identity_cache()
        setup_neutron_cache("RegionOne", "test_project_id")
        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "setup_network": True,
            "region": "RegionOne",
        }

        action = NewProjectDefaultNetworkAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        # Now we add the project data as this is where the project
        # would be created:
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        setup_identity_cache(projects=[project])

        task.cache = {"project_id": "test_project_id"}

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(
            action.action.cache,
            {
                "network_id_RegionOne": "net_id_0",
                "port_id_RegionOne": "port_id_3",
                "router_id_RegionOne": "router_id_2",
                "subnet_id_RegionOne": "subnet_id_1",
            },
        )

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 1
        )

    def test_new_project_network_setup_no_id(self):
        """
        No project id given, should do nothing.
        """
        setup_identity_cache()
        setup_neutron_cache("RegionOne", "test_project_id")
        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "setup_network": True,
            "region": "RegionOne",
        }

        action = NewProjectDefaultNetworkAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, False)

        self.assertEqual(action.action.cache, {})

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 0
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 0
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 0
        )

    def test_new_project_network_setup_no_setup(self):
        """
        Told not to setup, should do nothing.
        """
        setup_identity_cache()
        setup_neutron_cache("RegionOne", "test_project_id")
        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "setup_network": False,
            "region": "RegionOne",
        }

        action = NewProjectDefaultNetworkAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        # Now we add the project data as this is where the project
        # would be created:
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        setup_identity_cache(projects=[project])

        task.cache = {"project_id": "test_project_id"}

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(action.action.cache, {})

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 0
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 0
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 0
        )

    def test_new_project_network_setup_fail(self):
        """
        Should fail, but on re_approve will continue where it left off.
        """
        setup_identity_cache()
        setup_neutron_cache("RegionOne", "test_project_id")
        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "setup_network": True,
            "region": "RegionOne",
        }

        action = NewProjectDefaultNetworkAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        neutron_cache["RegionOne"]["test_project_id"]["routers"] = []

        # Now we add the project data as this is where the project
        # would be created:
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        setup_identity_cache(projects=[project])

        task.cache = {"project_id": "test_project_id"}

        try:
            action.approve()
            self.fail("Shouldn't get here.")
        except Exception:
            pass

        self.assertEqual(
            action.action.cache,
            {
                "network_id_RegionOne": "net_id_0",
                "subnet_id_RegionOne": "subnet_id_1",
            },
        )

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 0
        )

        neutron_cache["RegionOne"]["test_project_id"]["routers"] = {}

        action.approve()

        self.assertEqual(
            action.action.cache,
            {
                "network_id_RegionOne": "net_id_0",
                "port_id_RegionOne": "port_id_3",
                "router_id_RegionOne": "router_id_2",
                "subnet_id_RegionOne": "subnet_id_1",
            },
        )

        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["networks"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["routers"]), 1
        )
        self.assertEqual(
            len(neutron_cache["RegionOne"]["test_project_id"]["subnets"]), 1
        )

    def test_set_quota(self):
        """
        Base case, sets quota on all services of the cached project id.
        """
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        setup_identity_cache(projects=[project])
        setup_mock_caches("RegionOne", "test_project_id")

        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        task.cache = {"project_id": "test_project_id"}

        action = SetProjectQuotaAction({}, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        # check the quotas were updated
        cinderquota = cinder_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 5000)
        novaquota = nova_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 65536)
        neutronquota = neutron_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 3)

        # RegionThree, cinder only
        self.assertFalse("RegionThree" in nova_cache)
        r2_cinderquota = cinder_cache["RegionThree"]["test_project_id"]["quota"]
        self.assertEqual(r2_cinderquota["gigabytes"], 50001)
        self.assertEqual(r2_cinderquota["snapshots"], 600)
        self.assertEqual(r2_cinderquota["volumes"], 200)


@mock.patch("adjutant.common.user_store.IdentityManager", FakeManager)
@mock.patch("adjutant.common.openstack_clients.get_neutronclient", get_fake_neutron)
@mock.patch("adjutant.common.openstack_clients.get_novaclient", get_fake_novaclient)
@mock.patch("adjutant.common.openstack_clients.get_cinderclient", get_fake_cinderclient)
@mock.patch(
    "adjutant.common.openstack_clients.get_octaviaclient", get_fake_octaviaclient
)
@mock.patch("adjutant.common.openstack_clients.get_troveclient", get_fake_troveclient)
class QuotaActionTests(AdjutantTestCase):
    def test_update_quota(self):
        """
        Sets a new quota on all services of a project in a single region
        """
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        user = mock.Mock()
        user.id = "user_id"
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = "default"
        user.password = "test_password"

        setup_identity_cache(projects=[project], users=[user])
        setup_mock_caches("RegionOne", "test_project_id")

        # Test sending to only a single region
        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "project_id": "test_project_id",
            "size": "medium",
            "regions": ["RegionOne"],
            "user_id": user.id,
        }

        action = UpdateProjectQuotasAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        # check the quotas were updated
        cinderquota = cinder_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 10000)
        novaquota = nova_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 327680)
        neutronquota = neutron_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 5)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.quota.services": [
                {
                    "operation": "override",
                    "value": {
                        "RegionOne": [],
                        "*": ["cinder", "neutron", "nova"],
                    },
                },
            ],
        },
    )
    def test_update_quota_fail_disabled_region(self):
        """
        Check that a quota update for a region for which quota management
        is disabled is not valid, or performed.
        """
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        user = mock.Mock()
        user.id = "user_id"
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = "default"
        user.password = "test_password"

        setup_identity_cache(projects=[project], users=[user])
        setup_mock_caches("RegionOne", "test_project_id")

        # Test sending to only a single region
        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "project_id": "test_project_id",
            "size": "large",
            "regions": ["RegionOne"],
            "user_id": user.id,
        }

        action = UpdateProjectQuotasAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

        # check the quotas were updated
        cinderquota = cinder_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 5000)
        novaquota = nova_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 65536)
        neutronquota = neutron_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 3)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.quota.services": [
                {"operation": "override", "value": {}},
            ],
        },
    )
    def test_update_quota_fail_disabled(self):
        """
        Check that a quota update tasks are not valid or performed
        when quota management is disabled completely.
        """
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        user = mock.Mock()
        user.id = "user_id"
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = "default"
        user.password = "test_password"

        setup_identity_cache(projects=[project], users=[user])
        setup_mock_caches("RegionOne", "test_project_id")

        # Test sending to only a single region
        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "project_id": "test_project_id",
            "size": "large",
            "regions": ["RegionOne"],
            "user_id": user.id,
        }

        action = UpdateProjectQuotasAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

        # check the quotas were updated
        cinderquota = cinder_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 5000)
        novaquota = nova_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 65536)
        neutronquota = neutron_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 3)

    def test_update_quota_multi_region(self):
        """
        Sets a new quota on all services of a project in multiple regions
        """
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        user = mock.Mock()
        user.id = "user_id"
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = "default"
        user.password = "test_password"

        setup_identity_cache(projects=[project], users=[user])
        setup_mock_caches("RegionOne", project.id)
        setup_mock_caches("RegionTwo", project.id)

        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "project_id": "test_project_id",
            "size": "large",
            "domain_id": "default",
            "regions": ["RegionOne", "RegionTwo"],
            "user_id": "user_id",
        }

        action = UpdateProjectQuotasAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        # check the quotas were updated
        cinderquota = cinder_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 50000)
        novaquota = nova_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 655360)
        neutronquota = neutron_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 10)

        cinderquota = cinder_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 50000)
        novaquota = nova_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 655360)
        neutronquota = neutron_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 10)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.quota.services": [
                {
                    "operation": "override",
                    "value": {
                        "RegionTwo": [],
                        "*": ["cinder", "neutron", "nova"],
                    },
                },
            ],
        },
    )
    def test_update_quota_multi_region_one_disabled(self):
        """
        Check that when a request to update multiple regions at once
        and one of the regions have quota management disabled,
        only the enabled regions have their quotas updated.
        """
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        user = mock.Mock()
        user.id = "user_id"
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = "default"
        user.password = "test_password"

        setup_identity_cache(projects=[project], users=[user])
        setup_mock_caches("RegionOne", project.id)
        setup_mock_caches("RegionTwo", project.id)

        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "project_id": "test_project_id",
            "size": "large",
            "domain_id": "default",
            "regions": ["RegionOne", "RegionTwo"],
            "user_id": "user_id",
        }

        action = UpdateProjectQuotasAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        # check the quotas were updated
        cinderquota = cinder_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 50000)
        novaquota = nova_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 655360)
        neutronquota = neutron_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 10)

        cinderquota = cinder_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 5000)
        novaquota = nova_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 65536)
        neutronquota = neutron_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 3)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.quota.services": [
                {"operation": "override", "value": {}},
            ],
        },
    )
    def test_update_quota_multi_region_disabled(self):
        """
        Check that if a task to update quotas for multiple regions at once
        is initiated but quota management is disabled, no regions' quotas
        are updated.
        """
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        user = mock.Mock()
        user.id = "user_id"
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = "default"
        user.password = "test_password"

        setup_identity_cache(projects=[project], users=[user])
        setup_mock_caches("RegionOne", project.id)
        setup_mock_caches("RegionTwo", project.id)

        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "project_id": "test_project_id",
            "size": "large",
            "domain_id": "default",
            "regions": ["RegionOne", "RegionTwo"],
            "user_id": "user_id",
        }

        action = UpdateProjectQuotasAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

        # check the quotas were updated
        cinderquota = cinder_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 5000)
        novaquota = nova_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 65536)
        neutronquota = neutron_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 3)

        cinderquota = cinder_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 5000)
        novaquota = nova_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 65536)
        neutronquota = neutron_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 3)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.quota.sizes_ascending": [
                {"operation": "override", "value": []},
            ],
        },
    )
    def test_update_quota_not_in_sizes_asc(self):
        """
        Tests that the quota will still update to a size even if it is not
        placed in QUOTA_SIZES_ASC
        """

        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        user = mock.Mock()
        user.id = "user_id"
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = "default"
        user.password = "test_password"

        setup_identity_cache(projects=[project], users=[user])
        setup_mock_caches("RegionOne", project.id)
        setup_mock_caches("RegionTwo", project.id)

        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "project_id": "test_project_id",
            "size": "large",
            "domain_id": "default",
            "regions": ["RegionOne", "RegionTwo"],
        }

        action = UpdateProjectQuotasAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        # check the quotas were updated
        cinderquota = cinder_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 50000)
        novaquota = nova_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 655360)
        neutronquota = neutron_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 10)

        cinderquota = cinder_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 50000)
        novaquota = nova_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 655360)
        neutronquota = neutron_cache["RegionTwo"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 10)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.quota.services": [
                {
                    "operation": "override",
                    "value": {"*": ["cinder", "neutron", "nova", "octavia", "trove"]},
                }
            ]
        },
    )
    def test_update_quota_extra_services(self):
        """Tests the quota update of extra services over and above
        core openstack services.
        """
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        user = mock.Mock()
        user.id = "user_id"
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = "default"
        user.password = "test_password"

        setup_identity_cache(projects=[project], users=[user])
        setup_mock_caches("RegionOne", project.id)

        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "project_id": "test_project_id",
            "size": "large",
            "domain_id": "default",
            "regions": ["RegionOne"],
        }

        action = UpdateProjectQuotasAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        # check the quotas were updated
        cinderquota = cinder_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(cinderquota["gigabytes"], 50000)
        novaquota = nova_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(novaquota["ram"], 655360)
        neutronquota = neutron_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(neutronquota["network"], 10)
        octaviaquota = octavia_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(octaviaquota["load_balancer"], 10)
        trove_quota = trove_cache["RegionOne"]["test_project_id"]["quota"]
        self.assertEqual(trove_quota["instances"], 20)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.quota.services": [
                {
                    "operation": "override",
                    "value": {"*": ["cinder", "neutron", "nova", "octavia", "trove"]},
                }
            ]
        },
    )
    def test_quota_downgrade_fails_when_usage_exceeds_requested_quota(self):
        """Ensures that a quota change will fail validation when the
        current usage exceeds the requested quota.
        """
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        user = mock.Mock()
        user.id = "user_id"
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = "default"
        user.password = "test_password"

        setup_identity_cache(projects=[project], users=[user])
        setup_mock_caches("RegionOne", project.id)

        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        data = {
            "project_id": "test_project_id",
            "size": "small",
            "domain_id": "default",
            "regions": ["RegionOne"],
        }

        # setup 2 load balancers
        octavia_cache["RegionOne"][project.id]["load_balancer"] = [
            {"id": "fake_id"},
            {"id": "fake_id2"},
        ]

        trove_cache["RegionOne"][project.id]["instances"] = [
            {"id": "fake_id"},
            {"id": "fake_id2"},
            {"id": "fake_id3"},
            {"id": "fake_id4"},
        ]

        action = UpdateProjectQuotasAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

        # check the quotas were updated
        octaviaquota = octavia_cache["RegionOne"]["test_project_id"]["quota"]
        trove_quota = trove_cache["RegionOne"]["test_project_id"]["quota"]

        # Still set to default
        self.assertEqual(octaviaquota["load_balancer"], 1)
        self.assertEqual(trove_quota["instances"], 3)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {
                    "operation": "override",
                    "value": False,
                }
            ]
        },
    )
    def test_update_quota_username_not_email(self):
        """
        Test that the action correctly handles its username is not email case.
        """

        project = FakeProject(name="test_project")
        user = FakeUser(
            name="test",
            password="123",
            email="test@example.com",
        )
        setup_identity_cache(projects=[project], users=[user])
        setup_mock_caches("RegionOne", "test_project_id")

        task = Task.objects.create(
            keystone_user={"user_id": user.id, "roles": ["admin"]}
        )

        data = {
            "project_id": "test_project_id",
            "size": "medium",
            "regions": ["RegionOne"],
            "user_id": user.id,
        }
        action = UpdateProjectQuotasAction(data, task=task, order=1)

        user_email = action.get_email()
        self.assertEqual(user_email, user.email)

        # Now we reset the user/task/action and try without an email
        user = FakeUser(
            name="test",
            password="123",
        )
        setup_identity_cache(projects=[project], users=[user])
        task = Task.objects.create(
            keystone_user={"user_id": user.id, "roles": ["admin"]}
        )
        action = UpdateProjectQuotasAction(data, task=task, order=1)

        user_email = action.get_email()
        self.assertEqual(user_email, None)
