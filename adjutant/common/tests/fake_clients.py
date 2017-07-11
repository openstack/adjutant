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

import mock


identity_temp_cache = {}

neutron_cache = {}
nova_cache = {}
cinder_cache = {}


def setup_temp_cache(projects, users):
    default_domain = mock.Mock()
    default_domain.id = 'default'
    default_domain.name = 'Default'

    admin_user = mock.Mock()
    admin_user.id = 'user_id_0'
    admin_user.name = 'admin'
    admin_user.password = 'password'
    admin_user.email = 'admin@example.com'
    admin_user.domain = default_domain.id

    users.update({admin_user.id: admin_user})

    region_one = mock.Mock()
    region_one.id = 'RegionOne'
    region_one.name = 'RegionOne'

    region_two = mock.Mock()
    region_two.id = 'RegionTwo'

    global identity_temp_cache

    # TODO(adriant): region and project keys are name, should be ID.
    identity_temp_cache = {
        'i': 1,
        'users': users,
        'projects': projects,
        'roles': {
            '_member_': '_member_',
            'admin': 'admin',
            'project_admin': 'project_admin',
            'project_mod': 'project_mod',
            'heat_stack_owner': 'heat_stack_owner'
        },
        'regions': {
            'RegionOne': region_one,
            'RegionTwo': region_two
        },
        'domains': {
            default_domain.id: default_domain,
        },
    }


class FakeManager(object):

    def _project_from_id(self, project):
        if isinstance(project, mock.Mock):
            return project
        else:
            return self.get_project(project)

    def _role_from_id(self, role):
        if isinstance(role, mock.Mock):
            return role
        else:
            return self.get_role(role)

    def _user_from_id(self, user):
        if isinstance(user, mock.Mock):
            return user
        else:
            return self.get_user(user)

    def _domain_from_id(self, domain):
        if isinstance(domain, mock.Mock):
            return domain
        else:
            return self.get_domain(domain)

    def find_user(self, name, domain):
        domain = self._domain_from_id(domain)
        global identity_temp_cache
        for user in identity_temp_cache['users'].values():
            if user.name == name and user.domain == domain.id:
                return user
        return None

    def get_user(self, user_id):
        global identity_temp_cache
        return identity_temp_cache['users'].get(user_id, None)

    def list_users(self, project):
        project = self._project_from_id(project)
        global identity_temp_cache
        roles = identity_temp_cache['projects'][project.name].roles
        users = []

        for user_id, user_roles in roles.items():
            user = self.get_user(user_id)
            user.roles = []

            for role in user_roles:
                r = mock.Mock()
                r.name = role
                user.roles.append(r)

            users.append(user)
        return users

    def create_user(self, name, password, email, created_on,
                    domain='default', default_project=None):
        domain = self._domain_from_id(domain)
        default_project = self._project_from_id(default_project)
        global identity_temp_cache
        user = mock.Mock()
        user.id = "user_id_%s" % int(identity_temp_cache['i'])
        user.name = name
        user.password = password
        user.email = email
        user.domain = domain.id
        user.default_project = default_project
        identity_temp_cache['users'][user.id] = user

        identity_temp_cache['i'] += 0.5
        return user

    def update_user_password(self, user, password):
        user = self._user_from_id(user)
        user.password = password

    def update_user_name(self, user, username):
        user = self._user_from_id(user)
        user.name = username

    def update_user_email(self, user, email):
        user = self._user_from_id(user)
        user.email = email

    def enable_user(self, user):
        user = self._user_from_id(user)
        user.enabled = True

    def disable_user(self, user):
        user = self._user_from_id(user)
        user.enabled = False

    def find_role(self, name):
        global identity_temp_cache
        if identity_temp_cache['roles'].get(name, None):
            role = mock.Mock()
            role.name = name
            return role
        return None

    def get_roles(self, user, project):
        user = self._user_from_id(user)
        project = self._project_from_id(project)
        try:
            roles = []
            for role in project.roles[user.id]:
                r = mock.Mock()
                r.name = role
                roles.append(r)
            return roles
        except KeyError:
            return []

    def get_all_roles(self, user):
        user = self._user_from_id(user)
        global identity_temp_cache
        projects = {}
        for project in identity_temp_cache['projects'].values():
            projects[project.id] = []
            for role in project.roles[user.id]:
                r = mock.Mock()
                r.name = role
                projects[project.id].append(r)

        return projects

    def add_user_role(self, user, role, project):
        user = self._user_from_id(user)
        role = self._role_from_id(role)
        project = self._project_from_id(project)
        try:
            project.roles[user.id].append(role.name)
        except KeyError:
            project.roles[user.id] = [role.name]

    def remove_user_role(self, user, role, project):
        user = self._user_from_id(user)
        role = self._role_from_id(role)
        project = self._project_from_id(project)
        try:
            project.roles[user.id].remove(role.name)
        except KeyError:
            pass

    def find_project(self, project_name, domain):
        domain = self._domain_from_id(domain)
        global identity_temp_cache
        for project in identity_temp_cache['projects'].values():
            if project.name == project_name and project.domain == domain.id:
                return project
        return None

    def get_project(self, project_id):
        global identity_temp_cache
        for project in identity_temp_cache['projects'].values():
            if project.id == project_id:
                return project

    def create_project(self, project_name, created_on, parent=None,
                       domain='default', p_id=None):
        parent = self._project_from_id(parent)
        domain = self._domain_from_id(domain)
        global identity_temp_cache
        project = mock.Mock()
        if p_id:
            project.id = p_id
        else:
            identity_temp_cache['i'] += 0.5
            project.id = "project_id_%s" % int(identity_temp_cache['i'])
        project.name = project_name
        if parent:
            project.parent = parent.id
        else:
            project.parent = domain.id
        project.domain = domain.id
        project.roles = {}
        identity_temp_cache['projects'][project_name] = project
        return project

    def update_project(self, project, **kwargs):
        project = self._project_from_id(project)
        for key, arg in kwargs.items():
            if arg is not None:
                setattr(project, key, arg)
        return project

    def find_domain(self, domain_name):
        global identity_temp_cache
        for domain in identity_temp_cache['domains'].values():
            if domain.name == domain_name:
                return domain
        return None

    def get_domain(self, domain_id):
        global identity_temp_cache
        return identity_temp_cache['domains'].get(domain_id, None)

    def get_region(self, region_id):
        global identity_temp_cache
        return identity_temp_cache['regions'].get(region_id, None)

    def list_regions(self):
        global identity_temp_cache
        return identity_temp_cache['regions'].values()


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

        def get(self, tenant_id):
            return self.LimitFake(self.data, tenant_id)

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
