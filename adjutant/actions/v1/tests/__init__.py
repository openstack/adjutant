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

from django.conf import settings

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

        def get(self, project_id):
            return self.QuotaSet(
                self.service._cache[self.service.region][project_id]['quota'])

        class QuotaSet(object):
            def __init__(self, data):
                self.data = data

            def to_dict(self):
                return self.data

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

    def __init__(self, region):
        self.region = region

    def create_network(self, body):
        global neutron_cache
        project_id = body['network']['tenant_id']
        net = {'network': {'id': 'net_id_%s' % neutron_cache['RegionOne']['i'],
                           'body': body}}
        net_id = net['network']['id']
        neutron_cache['RegionOne'][project_id]['networks'][net_id] = net
        neutron_cache['RegionOne']['i'] += 1
        return net

    def create_subnet(self, body):
        global neutron_cache
        project_id = body['subnet']['tenant_id']
        subnet = {'subnet': {'id': 'subnet_id_%s'
                             % neutron_cache['RegionOne']['i'],
                             'body': body}}
        sub_id = subnet['subnet']['id']
        neutron_cache['RegionOne'][project_id]['subnets'][sub_id] = subnet
        neutron_cache['RegionOne']['i'] += 1
        return subnet

    def create_router(self, body):
        global neutron_cache
        project_id = body['router']['tenant_id']
        router = {'router': {'id': 'router_id_%s'
                             % neutron_cache['RegionOne']['i'],
                             'body': body}}
        router_id = router['router']['id']
        neutron_cache['RegionOne'][project_id]['routers'][router_id] = router
        neutron_cache['RegionOne']['i'] += 1
        return router

    def add_interface_router(self, router_id, body):
        global neutron_cache
        port_id = "port_id_%s" % neutron_cache['RegionOne']['i']
        neutron_cache['RegionOne']['i'] += 1
        interface = {
            'port_id': port_id,
            'id': router_id,
            'subnet_id': body['subnet_id']}
        return interface

    def update_quota(self, project_id, body):
        global neutron_cache
        if self.region not in neutron_cache:
            neutron_cache[self.region] = {}
        if project_id not in neutron_cache[self.region]:
            neutron_cache[self.region][project_id] = {}

        if 'quota' not in neutron_cache[self.region][project_id]:
            neutron_cache[self.region][project_id]['quota'] = {}

        quota = neutron_cache[self.region][project_id]['quota']
        quota.update(body['quota'])

    def show_quota(self, project_id):
        return {"quota": neutron_cache[self.region][project_id]['quota']}

    def list_networks(self, tenant_id):
        return neutron_cache[self.region][tenant_id]

    def list_routers(self, tenant_id):
        return neutron_cache[self.region][tenant_id]

    def list_subnets(self, tenant_id=0):
        return neutron_cache[self.region][tenant_id]

    def list_security_groups(self, tenant_id=0):
        return neutron_cache[self.region][tenant_id]

    def list_floatingips(self, tenant_id=0):
        return neutron_cache[self.region][tenant_id]

    def list_security_group_rules(self, tenant_id=0):
        return neutron_cache[self.region][tenant_id]

    def list_ports(self, tenant_id=0):
        return neutron_cache[self.region][tenant_id]


class FakeNovaClient(FakeOpenstackClient):

    def __init__(self, region):
        global nova_cache
        super(FakeNovaClient, self).__init__(region, nova_cache)
        self.limits = self.LimitFakers(nova_cache[region])

    class LimitFakers(object):
        def __init__(self, data):
            self.data = data

        def get(self, project_id):
            return self.LimitFake(self.data, project_id)

        class LimitFake(object):
            def __init__(self, data, project_id):
                self.project_id = project_id
                self.data = data

            def to_dict(self):
                return self.data[self.project_id]


class FakeCinderClient(FakeOpenstackClient):
    class FakeResourceGroup(object):
        """ Stub class to represent volumes and snapshots """

        def __init__(self, region, cache_key):
            self.region = region
            self.key = cache_key

        def list(self, search_opts=None):
            if search_opts:
                project_id = search_opts['project_id']
                # TODO: This should return data from the cache so that it
                # can be set up properly
                global cinder_cache
                return cinder_cache[self.region][project_id][self.key]

    def __init__(self, region):
        global cinder_cache
        self.region = region
        self._cache = cinder_cache
        self.quotas = FakeOpenstackClient.Quotas(self)
        self.volumes = self.FakeResourceGroup(region, 'volumes')
        self.volume_snapshots = self.FakeResourceGroup(region,
                                                       'volume_snapshots')


class FakeResource(object):
    """ Stub class to represent an individual instance of a volume or
    snapshot """

    def __init__(self, size):
        self.size = size


def setup_neutron_cache(region, project_id):
    global neutron_cache
    if region not in neutron_cache:
        neutron_cache[region] = {'i': 0}
    else:
        neutron_cache[region]['i'] = 0
    if project_id not in neutron_cache[region]:
        neutron_cache[region][project_id] = {}

    neutron_cache[region][project_id] = {
        'networks': {},
        'subnets': {},
        'routers': {},
        'security_groups': {},
        'floatingips': {},
        'security_group_rules': {},
        'ports': {},
    }

    neutron_cache[region][project_id]['quota'] = dict(
        settings.PROJECT_QUOTA_SIZES['small']['neutron'])


def setup_cinder_cache(region, project_id):
    global cinder_cache
    if region not in cinder_cache:
        cinder_cache[region] = {}
    if project_id not in cinder_cache[region]:
        cinder_cache[region][project_id] = {}

    cinder_cache[region][project_id] = {
        'volumes': [],
        'volume_snapshots': [],
    }

    cinder_cache[region][project_id]['quota'] = dict(
        settings.PROJECT_QUOTA_SIZES['small']['cinder'])


def setup_nova_cache(region, project_id):
    global nova_cache
    if region not in nova_cache:
        nova_cache[region] = {}
    if project_id not in nova_cache[region]:
        nova_cache[region][project_id] = {}

    # Mocking the nova limits api
    nova_cache[region][project_id] = {
        'absolute': {
            "totalInstancesUsed": 0,
            "totalFloatingIpsUsed": 0,
            "totalRAMUsed": 0,
            "totalCoresUsed": 0,
            "totalSecurityGroupsUsed": 0
        }
    }
    nova_cache[region][project_id]['quota'] = dict(
        settings.PROJECT_QUOTA_SIZES['small']['nova'])


def setup_quota_cache(region_name, project_id, size='small'):
    """ Sets up the quota cache for a given region and project """
    global cinder_cache

    if region_name not in cinder_cache:
        cinder_cache[region_name] = {}

    if project_id not in cinder_cache[region_name]:
        cinder_cache[region_name][project_id] = {
            'quota': {}
        }

    cinder_cache[region_name][project_id]['quota'] = dict(
        settings.PROJECT_QUOTA_SIZES[size]['cinder'])

    global nova_cache
    if region_name not in nova_cache:
        nova_cache[region_name] = {}

    if project_id not in nova_cache[region_name]:
        nova_cache[region_name][project_id] = {
            'quota': {}
        }

    nova_cache[region_name][project_id]['quota'] = dict(
        settings.PROJECT_QUOTA_SIZES[size]['nova'])

    global neutron_cache
    if region_name not in neutron_cache:
        neutron_cache[region_name] = {}

    if project_id not in neutron_cache[region_name]:
        neutron_cache[region_name][project_id] = {
            'quota': {}
        }

    neutron_cache[region_name][project_id]['quota'] = dict(
        settings.PROJECT_QUOTA_SIZES[size]['neutron'])


def setup_mock_caches(region, project_id):
    setup_nova_cache(region, project_id)
    setup_cinder_cache(region, project_id)
    setup_neutron_cache(region, project_id)


def get_fake_neutron(region):
    return FakeNeutronClient(region)


def get_fake_novaclient(region):
    return FakeNovaClient(region)


def get_fake_cinderclient(region):
    global cinder_cache
    return FakeCinderClient(region)
