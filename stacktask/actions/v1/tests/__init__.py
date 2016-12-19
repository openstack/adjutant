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
    neutron_cache.clear()
    neutron_cache.update({
        'i': 0,
        'networks': {},
        'subnets': {},
        'routers': {},
    })


def get_fake_neutron(region):
    return FakeNeutronClient()


def get_fake_novaclient(region):
    global nova_cache
    return FakeOpenstackClient(region, nova_cache)


def get_fake_cinderclient(region):
    global cinder_cache
    return FakeOpenstackClient(region, cinder_cache)
