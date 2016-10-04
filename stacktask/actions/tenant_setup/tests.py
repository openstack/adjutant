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
    NewDefaultNetworkAction, NewProjectDefaultNetworkAction,
    AddDefaultUsersToProjectAction, SetProjectQuotaAction)
from stacktask.api.models import Task
from stacktask.api.v1 import tests
from stacktask.api.v1.tests import FakeManager, setup_temp_cache


neutron_cache = {}
nova_cache = {}
cinder_cache = {}


class FakeOpenstackClient(object):
    class Quotas(object):
        """ Stub class for testing quotas """
        def __init__(self, service):
            self.service = service

        def update(self, project_id, **kwargs):
            self.service.update_quota(project_id, **kwargs)

    def __init__(self, region, cache):
        self.region = region
        self._cache = cache
        self.quotas = FakeOpenstackClient.Quotas(self)

    def update_quota(self, project_id, **kwargs):
        if self.region not in self._cache:
            self._cache[self.region] = {}
        if project_id not in self._cache[self.region]:
            self._cache[self.region][project_id] = {
                'quota': {}
            }
        quota = self._cache[self.region][project_id]['quota']
        quota.update(kwargs)


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

    def update_quota(self, project_id, body):
        global neutron_cache
        if project_id not in neutron_cache:
            neutron_cache[project_id] = {}
        if 'quota' not in neutron_cache[project_id]:
            neutron_cache[project_id]['quota'] = {}

        quota = neutron_cache[project_id]['quota']
        quota.update(body['quota'])


def setup_neutron_cache():
    global neutron_cache
    neutron_cache = {
        'i': 0,
        'networks': {},
        'subnets': {},
        'routers': {},
    }


def get_fake_neutron(region):
    return FakeNeutronClient()


def get_fake_novaclient(region):
    global nova_cache
    return FakeOpenstackClient(region, nova_cache)


def get_fake_cinderclient(region):
    global cinder_cache
    return FakeOpenstackClient(region, cinder_cache)


class ProjectSetupActionTests(TestCase):

    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    @mock.patch(
        'stacktask.actions.tenant_setup.models.' +
        'openstack_clients.get_neutronclient',
        get_fake_neutron)
    def test_network_setup(self):
        """
        Base case, setup a new network , no issues.
        """
        setup_neutron_cache()
        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin'],
                'project_id': 'test_project_id'})

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        data = {
            'setup_network': True,
            'region': 'RegionOne',
            'project_id': 'test_project_id',
        }

        action = NewDefaultNetworkAction(
            data, task=task, order=1)

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
    @mock.patch(
        'stacktask.actions.tenant_setup.models.' +
        'openstack_clients.get_neutronclient',
        get_fake_neutron)
    def test_network_setup_no_setup(self):
        """
        Told not to setup, should do nothing.
        """
        setup_neutron_cache()
        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin'],
                'project_id': 'test_project_id'})

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        data = {
            'setup_network': False,
            'region': 'RegionOne',
            'project_id': 'test_project_id',
        }

        action = NewDefaultNetworkAction(
            data, task=task, order=1)

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
    @mock.patch(
        'stacktask.actions.tenant_setup.models.' +
        'openstack_clients.get_neutronclient',
        get_fake_neutron)
    def test_network_setup_fail(self):
        """
        Should fail, but on re_approve will continue where it left off.
        """
        setup_neutron_cache()
        global neutron_cache
        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin'],
                'project_id': 'test_project_id'})

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        data = {
            'setup_network': True,
            'region': 'RegionOne',
            'project_id': 'test_project_id',
        }

        action = NewDefaultNetworkAction(
            data, task=task, order=1)

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
    @mock.patch(
        'stacktask.actions.tenant_setup.models.' +
        'openstack_clients.get_neutronclient',
        get_fake_neutron)
    def test_new_project_network_setup(self):
        """
        Base case, setup network after a new project, no issues.
        """
        setup_neutron_cache()
        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'setup_network': True,
            'region': 'RegionOne',
        }

        action = NewProjectDefaultNetworkAction(
            data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        # Now we add the project data as this is where the project
        # would be created:
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task.cache = {'project_id': "test_project_id"}

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
    @mock.patch(
        'stacktask.actions.tenant_setup.models.' +
        'openstack_clients.get_neutronclient',
        get_fake_neutron)
    def test_new_project_network_setup_no_id(self):
        """
        No project id given, should do nothing.
        """
        setup_neutron_cache()
        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'setup_network': True,
            'region': 'RegionOne',
        }

        action = NewProjectDefaultNetworkAction(
            data, task=task, order=1)

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
    @mock.patch(
        'stacktask.actions.tenant_setup.models.' +
        'openstack_clients.get_neutronclient',
        get_fake_neutron)
    def test_new_project_network_setup_no_setup(self):
        """
        Told not to setup, should do nothing.
        """
        setup_neutron_cache()
        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'setup_network': False,
            'region': 'RegionOne',
        }

        action = NewProjectDefaultNetworkAction(
            data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        # Now we add the project data as this is where the project
        # would be created:
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task.cache = {'project_id': "test_project_id"}

        action.post_approve()
        self.assertEquals(action.valid, True)

        self.assertEquals(action.action.cache, {})

        global neutron_cache
        self.assertEquals(len(neutron_cache['networks']), 0)
        self.assertEquals(len(neutron_cache['routers']), 0)
        self.assertEquals(len(neutron_cache['subnets']), 0)

    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    @mock.patch(
        'stacktask.actions.tenant_setup.models.' +
        'openstack_clients.get_neutronclient',
        get_fake_neutron)
    def test_new_project_network_setup_fail(self):
        """
        Should fail, but on re_approve will continue where it left off.
        """
        setup_neutron_cache()
        global neutron_cache
        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'setup_network': True,
            'region': 'RegionOne',
        }

        action = NewProjectDefaultNetworkAction(
            data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        neutron_cache['routers'] = []

        # Now we add the project data as this is where the project
        # would be created:
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task.cache = {'project_id': "test_project_id"}

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
    def test_add_default_users(self):
        """
        Base case, adds admin user with admin role to project.

        NOTE(adriant): both the lists of users, and the roles to add
        come from test_settings. This test assumes the conf setting of:
        default_users = ['admin']
        default_roles = ['admin']
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        task.cache = {'project_id': "test_project_id"}

        action = AddDefaultUsersToProjectAction(
            {'domain_id': 'default'}, task=task, order=1)

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
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        task.cache = {'project_id': "test_project_id"}

        action = AddDefaultUsersToProjectAction(
            {'domain_id': 'default'}, task=task, order=1)

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

    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    @mock.patch(
        'stacktask.actions.tenant_setup.models.' +
        'openstack_clients.get_neutronclient',
        get_fake_neutron)
    @mock.patch(
        'stacktask.actions.tenant_setup.models.' +
        'openstack_clients.get_novaclient',
        get_fake_novaclient)
    @mock.patch(
        'stacktask.actions.tenant_setup.models.' +
        'openstack_clients.get_cinderclient',
        get_fake_cinderclient)
    def test_set_quota(self):
        """
        Base case, sets quota on all services of the cached project id.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})
        setup_neutron_cache()

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        task.cache = {'project_id': "test_project_id"}

        action = SetProjectQuotaAction({}, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        # check the quotas were updated
        # This relies on test_settings heavily.
        cinderquota = cinder_cache['RegionOne']['test_project_id']['quota']
        self.assertEquals(cinderquota['gigabytes'], 5000)
        novaquota = nova_cache['RegionOne']['test_project_id']['quota']
        self.assertEquals(novaquota['ram'], 65536)
        neutronquota = neutron_cache['test_project_id']['quota']
        self.assertEquals(neutronquota['network'], 3)

        # RegionTwo, cinder only
        self.assertFalse('RegionTwo' in nova_cache)
        r2_cinderquota = cinder_cache['RegionTwo']['test_project_id']['quota']
        self.assertEquals(r2_cinderquota['gigabytes'], 73571)
        self.assertEquals(r2_cinderquota['snapshots'], 73572)
        self.assertEquals(r2_cinderquota['volumes'], 73573)
