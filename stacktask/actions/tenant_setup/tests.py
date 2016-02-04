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

from django.test import TestCase

import mock

from stacktask.actions.tenant_setup.models import (
    AddAdminToProject, DefaultProjectResources)
from stacktask.api.models import Task
from stacktask.api.v1 import tests
from stacktask.api.v1.tests import FakeManager, setup_temp_cache


neutron_cache = {}


class FakeNeutronClient(object):

    def create_network(self, body):
        global neutron_cache
        net = {'network': {'id': 'net_id_%s' % neutron_cache['i'],
                           'body': body}}
        neutron_cache['networks'][net['network']['id']] = net
        neutron_cache['i'] += 1
        return net

    def create_subnet(self, body):
        global neutron_cache
        subnet = {'subnet': {'id': 'subnet_id_%s' % neutron_cache['i'],
                             'body': body}}
        neutron_cache['subnets'][subnet['subnet']['id']] = subnet
        neutron_cache['i'] += 1
        return subnet

    def create_router(self, body):
        global neutron_cache
        router = {'router': {'id': 'router_id_%s' % neutron_cache['i'],
                             'body': body}}
        neutron_cache['routers'][router['router']['id']] = router
        neutron_cache['i'] += 1
        return router

    def add_interface_router(self, router_id, body):
        global neutron_cache
        router = neutron_cache['routers'][router_id]
        router['router']['interface'] = body
        return router


def setup_neutron_cache():
    global neutron_cache
    neutron_cache = {
        'i': 0,
        'networks': {},
        'subnets': {},
        'routers': {}
    }


def get_fake_neutron():
    return FakeNeutronClient()


class TenantSetupActionTests(TestCase):

    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    @mock.patch('stacktask.actions.tenant_setup.models.openstack_clients.get_neutronclient',
                get_fake_neutron)
    def test_resource_setup(self):
        """
        Base case, setup resources, no issues.
        """
        setup_neutron_cache()
        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        task.cache = {'project_id': "1"}

        data = {
            'setup_resources': True,
        }

        action = DefaultProjectResources(data, task=task,
                                         order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        self.assertEquals(
            action.action.cache,
            {'network_id': 'net_id_0',
             'router_id': 'router_id_2',
             'subnet_id': 'subnet_id_1'}
        )

        global neutron_cache
        self.assertEquals(len(neutron_cache['networks']), 1)
        self.assertEquals(len(neutron_cache['routers']), 1)
        self.assertEquals(len(neutron_cache['subnets']), 1)

    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    @mock.patch('stacktask.actions.tenant_setup.models.openstack_clients.get_neutronclient',
                get_fake_neutron)
    def test_resource_setup_no_id(self):
        """
        No project id given, should do nothing.
        """
        setup_neutron_cache()
        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'setup_resources': True,
        }

        action = DefaultProjectResources(data, task=task,
                                         order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, False)

        self.assertEquals(action.action.cache, {})

        global neutron_cache
        self.assertEquals(len(neutron_cache['networks']), 0)
        self.assertEquals(len(neutron_cache['routers']), 0)
        self.assertEquals(len(neutron_cache['subnets']), 0)

    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    @mock.patch('stacktask.actions.tenant_setup.models.openstack_clients.get_neutronclient',
                get_fake_neutron)
    def test_resource_setup_no_setup(self):
        """
        Told not to setup, should do nothing.
        """
        setup_neutron_cache()
        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'setup_resources': False,
        }

        task.cache = {'project_id': "1"}

        action = DefaultProjectResources(data, task=task,
                                         order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        self.assertEquals(action.action.cache, {})

        global neutron_cache
        self.assertEquals(len(neutron_cache['networks']), 0)
        self.assertEquals(len(neutron_cache['routers']), 0)
        self.assertEquals(len(neutron_cache['subnets']), 0)

    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    @mock.patch('stacktask.actions.tenant_setup.models.openstack_clients.get_neutronclient',
                get_fake_neutron)
    def test_resource_setup_fail(self):
        """
        Should fail, but on re_approve will continue where it left off.
        """
        setup_neutron_cache()
        global neutron_cache
        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'setup_resources': True,
        }

        task.cache = {'project_id': "1"}

        action = DefaultProjectResources(data, task=task,
                                         order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        neutron_cache['routers'] = []

        try:
            action.post_approve()
            self.fail("Shouldn't get here.")
        except Exception:
            pass

        self.assertEquals(
            action.action.cache,
            {'network_id': 'net_id_0',
             'subnet_id': 'subnet_id_1'}
        )

        self.assertEquals(len(neutron_cache['networks']), 1)
        self.assertEquals(len(neutron_cache['subnets']), 1)
        self.assertEquals(len(neutron_cache['routers']), 0)

        neutron_cache['routers'] = {}

        action.post_approve()

        self.assertEquals(
            action.action.cache,
            {'network_id': 'net_id_0',
             'router_id': 'router_id_2',
             'subnet_id': 'subnet_id_1'}
        )

        self.assertEquals(len(neutron_cache['networks']), 1)
        self.assertEquals(len(neutron_cache['routers']), 1)
        self.assertEquals(len(neutron_cache['subnets']), 1)

    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    def test_add_admin(self):
        """
        Base case, adds admin user with admin role to project.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        task.cache = {'project_id': "test_project_id"}

        action = AddAdminToProject({}, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(project.roles['user_id_0'], ['admin'])

    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    def test_add_admin_reapprove(self):
        """
        Ensure nothing happens or changes if rerun of approve.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        task.cache = {'project_id': "test_project_id"}

        action = AddAdminToProject({}, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(project.roles['user_id_0'], ['admin'])

        action.post_approve()
        self.assertEquals(action.valid, True)

        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(project.roles['user_id_0'], ['admin'])
