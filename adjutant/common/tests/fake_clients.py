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

from collections import namedtuple
from unittest import mock
from uuid import uuid4

from adjutant.config import CONF


identity_cache = {}
neutron_cache = {}
nova_cache = {}
cinder_cache = {}
octavia_cache = {}
trove_cache = {}


class FakeProject(object):
    def __init__(
        self,
        name,
        description="",
        domain_id="default",
        parent_id=None,
        enabled=True,
        is_domain=False,
        **kwargs,
    ):
        self.id = uuid4().hex
        self.name = name
        self.description = description
        self.domain_id = domain_id
        self.parent_id = parent_id
        self.enabled = enabled
        self.is_domain = is_domain

        # handle extra values
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeUser(object):
    def __init__(
        self,
        name,
        password="123",
        domain_id="default",
        enabled=True,
        default_project_id=None,
        **kwargs,
    ):
        self.id = uuid4().hex
        self.name = name
        self.password = password
        self.domain_id = domain_id
        self.enabled = enabled
        self.default_project_id = default_project_id

        # handle extra values
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeRole(object):
    def __init__(self, name):
        self.id = uuid4().hex
        self.name = name


class FakeCredential(object):
    def __init__(self, user_id, cred_type, blob, project_id=None):
        self.id = uuid4().hex
        self.user_id = user_id
        self.project_id = project_id
        self.type = cred_type
        self.blob = blob


class FakeRoleAssignment(object):
    def __init__(
        self, scope, role=None, role_name=None, user=None, group=None, inherited=False
    ):
        if role:
            self.role = role
        elif role_name:
            self.role = {"name": role_name}
        else:
            raise AttributeError("must supply 'role' or 'role_name'.")
        self.scope = scope
        self.user = user
        self.group = group
        if inherited:
            self.scope["OS-INHERIT:inherited_to"] = "projects"

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


def setup_identity_cache(
    projects=None, users=None, role_assignments=None, credentials=None, extra_roles=None
):
    if extra_roles is None:
        extra_roles = []
    if not projects:
        projects = []
    if not users:
        users = []
    if not role_assignments:
        role_assignments = []
    if not credentials:
        credentials = []

    default_domain = FakeProject(name="Default", is_domain=True)
    default_domain.id = "default"

    projects.append(default_domain)

    admin_user = FakeUser(
        name="admin",
        password="password",
        email="admin@example.com",
        domain_id=default_domain.id,
    )

    users.append(admin_user)

    roles = [
        FakeRole(name="member"),
        FakeRole(name="admin"),
        FakeRole(name="project_admin"),
        FakeRole(name="project_mod"),
        FakeRole(name="heat_stack_owner"),
    ] + extra_roles

    region_one = mock.Mock()
    region_one.id = "RegionOne"

    region_two = mock.Mock()
    region_two.id = "RegionTwo"

    global identity_cache

    identity_cache = {
        "users": {u.id: u for u in users},
        "new_users": [],
        "projects": {p.id: p for p in projects},
        "new_projects": [],
        "role_assignments": role_assignments,
        "new_role_assignments": [],
        "roles": {r.id: r for r in roles},
        "regions": {"RegionOne": region_one, "RegionTwo": region_two},
        "domains": {
            default_domain.id: default_domain,
        },
        "credentials": credentials,
    }


class FakeManager(object):
    def __init__(self):
        # TODO(adriant): decide if we want to have some function calls
        # throw errors if this is false.
        self.can_edit_users = CONF.identity.can_edit_users

    def _project_from_id(self, project):
        if isinstance(project, FakeProject):
            return project
        else:
            return self.get_project(project)

    def _role_from_id(self, role):
        if isinstance(role, FakeRole):
            return role
        else:
            return self.get_role(role)

    def _user_from_id(self, user):
        if isinstance(user, FakeUser):
            return user
        else:
            return self.get_user(user)

    def _domain_from_id(self, domain):
        if isinstance(domain, FakeProject) and domain.is_domain:
            return domain
        else:
            return self.get_domain(domain)

    def find_user(self, name, domain):
        domain = self._domain_from_id(domain)
        global identity_cache
        for user in identity_cache["users"].values():
            if user.name.lower() == name.lower() and user.domain_id == domain.id:
                return user
        return None

    def get_user(self, user_id):
        global identity_cache
        return identity_cache["users"].get(user_id, None)

    def list_users(self, project):
        project = self._project_from_id(project)
        global identity_cache
        users = {}

        for assignment in identity_cache["role_assignments"]:
            if assignment.scope["project"]["id"] == project.id:

                user = users.get(assignment.user["id"])
                if not user:
                    user = self.get_user(assignment.user["id"])
                    user.roles = []
                    user.inherited_roles = []
                    users[user.id] = user

                r = self.find_role(assignment.role["name"])

                if assignment.scope.get("OS-INHERIT:inherited_to"):
                    user.inherited_roles.append(r)
                else:
                    user.roles.append(r)

        return users.values()

    def list_inherited_users(self, project):
        project = self._project_from_id(project)
        global identity_cache
        users = {}

        while project.parent_id:
            project = self._project_from_id(project.parent_id)
            for assignment in identity_cache["role_assignments"]:
                if assignment.scope["project"]["id"] == project.id:
                    if not assignment.scope.get("OS-INHERIT:inherited_to"):
                        continue

                    user = users.get(assignment.user["id"])
                    if not user:
                        user = self.get_user(assignment.user["id"])
                        user.roles = []
                        user.inherited_roles = []
                        users[user.id] = user

                    r = self.find_role(assignment.role["name"])

                    user.roles.append(r)

        return users.values()

    def create_user(
        self, name, password, email, created_on, domain="default", default_project=None
    ):
        domain = self._domain_from_id(domain)
        default_project = self._project_from_id(default_project)
        global identity_cache
        user = FakeUser(
            name=name,
            password=password,
            email=email,
            domain_id=domain.id,
            default_project=default_project,
        )
        identity_cache["users"][user.id] = user
        identity_cache["new_users"].append(user)
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
        global identity_cache
        for role in identity_cache["roles"].values():
            if role.name == name:
                return role
        return None

    def get_roles(self, user, project, inherited=False):
        user = self._user_from_id(user)
        project = self._project_from_id(project)
        global identity_cache

        roles = []

        for assignment in identity_cache["role_assignments"]:
            if (
                assignment.user["id"] == user.id
                and assignment.scope["project"]["id"] == project.id
            ):

                if (
                    assignment.scope.get("OS-INHERIT:inherited_to") and not inherited
                ) or (
                    inherited and not assignment.scope.get("OS-INHERIT:inherited_to")
                ):
                    continue

                r = self.find_role(assignment.role["name"])
                roles.append(r)

        return roles

    def _get_roles_as_names(self, user, project, inherited=False):
        return [r.name for r in self.get_roles(user, project, inherited)]

    def get_all_roles(self, user):
        user = self._user_from_id(user)
        global identity_cache
        projects = {}
        for assignment in identity_cache["role_assignments"]:
            if assignment.user["id"] == user.id:
                r = self.find_role(assignment.role["name"])
                try:
                    projects[assignment.scope["project"]["id"]].append(r)
                except KeyError:
                    projects[assignment.scope["project"]["id"]] = [r]
        return projects

    def _make_role_assignment(self, user, role, project, inherited=False):
        scope = {"project": {"id": project.id}}
        if inherited:
            scope["OS-INHERIT:inherited_to"] = "projects"
        role_assignment = FakeRoleAssignment(
            scope=scope,
            role={"name": role.name},
            user={"id": user.id},
        )
        return role_assignment

    def add_user_role(self, user, role, project, inherited=False):
        user = self._user_from_id(user)
        role = self._role_from_id(role)
        project = self._project_from_id(project)

        role_assignment = self._make_role_assignment(user, role, project)

        global identity_cache

        if role_assignment not in identity_cache["role_assignments"]:
            identity_cache["role_assignments"].append(role_assignment)
            identity_cache["new_role_assignments"].append(role_assignment)

    def remove_user_role(self, user, role, project, inherited=False):
        user = self._user_from_id(user)
        role = self._role_from_id(role)
        project = self._project_from_id(project)

        role_assignment = self._make_role_assignment(
            user, role, project, inherited=inherited
        )

        global identity_cache

        if role_assignment in identity_cache["role_assignments"]:
            identity_cache["role_assignments"].remove(role_assignment)

    def find_project(self, project_name, domain):
        domain = self._domain_from_id(domain)
        global identity_cache
        for project in identity_cache["projects"].values():
            if (
                project.name.lower() == project_name.lower()
                and project.domain_id == domain.id
            ):
                return project
        return None

    def get_project(self, project_id, subtree_as_ids=False, parents_as_ids=False):
        global identity_cache
        project = identity_cache["projects"].get(project_id, None)

        if subtree_as_ids:
            subtree_list = []
            prev_layer = [
                project.id,
            ]
            current_layer = True
            while current_layer:
                current_layer = [
                    s_project.id
                    for s_project in identity_cache["projects"].values()
                    if project.parent_id in prev_layer
                ]
                prev_layer = current_layer
                subtree_list.append(current_layer)

            project.subtree_ids = subtree_list

        if parents_as_ids:
            parent_list = []
            parent_id = project.parent_id
            parent_list.append(parent_id)
            while identity_cache["projects"].get(parent_id, None):
                parent_id = identity_cache["projects"].get(parent_id, None)
                parent_list.append(parent_id)

            project.parent_ids = parent_list
            project.root = parent_id
            project.depth = len(parent_list)

        return project

    def create_project(
        self, project_name, created_on, parent=None, domain="default", description=""
    ):
        parent = self._project_from_id(parent)
        domain = self._domain_from_id(domain)
        global identity_cache

        project = FakeProject(
            name=project_name,
            created_on=created_on,
            description=description,
            domain_id=domain.id,
        )
        if parent:
            project.parent_id = parent.id
        identity_cache["projects"][project.id] = project
        identity_cache["new_projects"].append(project)
        return project

    def update_project(self, project, **kwargs):
        project = self._project_from_id(project)
        for key, arg in kwargs.items():
            if arg is not None:
                setattr(project, key, arg)
        return project

    def find_domain(self, domain_name):
        global identity_cache
        for domain in identity_cache["domains"].values():
            if domain.name.lower() == domain_name.lower():
                return domain
        return None

    def get_domain(self, domain_id):
        global identity_cache
        return identity_cache["domains"].get(domain_id, None)

    def get_region(self, region_id):
        global identity_cache
        return identity_cache["regions"].get(region_id, None)

    def list_regions(self):
        global identity_cache
        return identity_cache["regions"].values()

    def list_credentials(self, user_id, cred_type=None):
        global identity_cache
        found = []
        for cred in identity_cache["credentials"]:
            if cred.user_id == user_id:
                if cred_type and cred.type == cred_type:
                    found.append(cred)
                elif cred_type is None:
                    found.append(cred)
        return found

    def add_credential(self, user, cred_type, blob, project=None):
        global identity_cache
        user = self._user_from_id(user)
        project = self._project_from_id(project)
        cred = FakeCredential(user_id=user.id, blob=blob, cred_type=cred_type)
        if project:
            cred.project_id = project.id
        identity_cache["credentials"].append(cred)
        return cred

    def clear_credential_type(self, user_id, cred_type):
        global identity_cache
        found = []
        for cred in identity_cache["credentials"]:
            if cred.user_id == user_id and cred.type == cred_type:
                found.append(cred)
        for cred in found:
            identity_cache["credentials"].remove(cred)

    # TODO(adriant): Move this to a BaseIdentityManager class when
    #                it exists.
    def get_manageable_roles(self, user_roles=None):
        """Get roles which can be managed

        Given a list of user role names, returns a list of names
        that the user is allowed to manage.

        If user_roles is not given, returns all possible roles.
        """
        roles_mapping = CONF.identity.role_mapping
        if user_roles is None:
            all_roles = []
            for options in roles_mapping.values():
                all_roles += options
            return list(set(all_roles))

        # merge mapping lists to form a flat permitted roles list
        manageable_role_names = [
            mrole
            for role_name in user_roles
            if role_name in roles_mapping
            for mrole in roles_mapping[role_name]
        ]
        # a set has unique items
        manageable_role_names = set(manageable_role_names)
        return manageable_role_names


class FakeOpenstackClient(object):
    class Quotas(object):
        """Stub class for testing quotas"""

        def __init__(self, service):
            self.service = service

        def update(self, project_id, **kwargs):
            self.service.update_quota(project_id, **kwargs)

        def get(self, project_id):
            return self.QuotaSet(
                self.service._cache[self.service.region][project_id]["quota"]
            )

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
            self._cache[self.region][project_id] = {"quota": {}}
        quota = self._cache[self.region][project_id]["quota"]
        quota.update(kwargs)


class FakeNeutronClient(object):
    def __init__(self, region):
        self.region = region

    def create_network(self, body):
        global neutron_cache
        project_id = body["network"]["tenant_id"]
        net = {
            "network": {
                "id": "net_id_%s" % neutron_cache["RegionOne"]["i"],
                "body": body,
            }
        }
        net_id = net["network"]["id"]
        neutron_cache["RegionOne"][project_id]["networks"][net_id] = net
        neutron_cache["RegionOne"]["i"] += 1
        return net

    def create_subnet(self, body):
        global neutron_cache
        project_id = body["subnet"]["tenant_id"]
        subnet = {
            "subnet": {
                "id": "subnet_id_%s" % neutron_cache["RegionOne"]["i"],
                "body": body,
            }
        }
        sub_id = subnet["subnet"]["id"]
        neutron_cache["RegionOne"][project_id]["subnets"][sub_id] = subnet
        neutron_cache["RegionOne"]["i"] += 1
        return subnet

    def create_router(self, body):
        global neutron_cache
        project_id = body["router"]["tenant_id"]
        router = {
            "router": {
                "id": "router_id_%s" % neutron_cache["RegionOne"]["i"],
                "body": body,
            }
        }
        router_id = router["router"]["id"]
        neutron_cache["RegionOne"][project_id]["routers"][router_id] = router
        neutron_cache["RegionOne"]["i"] += 1
        return router

    def add_interface_router(self, router_id, body):
        global neutron_cache
        port_id = "port_id_%s" % neutron_cache["RegionOne"]["i"]
        neutron_cache["RegionOne"]["i"] += 1
        interface = {
            "port_id": port_id,
            "id": router_id,
            "subnet_id": body["subnet_id"],
        }
        return interface

    def update_quota(self, project_id, body):
        global neutron_cache
        if self.region not in neutron_cache:
            neutron_cache[self.region] = {}
        if project_id not in neutron_cache[self.region]:
            neutron_cache[self.region][project_id] = {}

        if "quota" not in neutron_cache[self.region][project_id]:
            neutron_cache[self.region][project_id]["quota"] = {}

        quota = neutron_cache[self.region][project_id]["quota"]
        quota.update(body["quota"])

    def show_quota(self, project_id):
        return {"quota": neutron_cache[self.region][project_id]["quota"]}

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


class FakeOctaviaClient(object):
    # {name in client call: name in response}
    resource_dict = {
        "load_balancer": "loadbalancers",
        "listener": "listeners",
        "member": "members",
        "pool": "pools",
        "health_monitor": "healthmonitors",
    }

    # NOTE(amelia): Using the current octavia client we will get back
    #               dicts for everything, rather than the resources the
    #               other clients wrap.
    #               Additionally the openstacksdk octavia implemenation
    #               does not have quota commands

    def __init__(self, region):
        global octavia_cache
        self.region = region
        if region not in octavia_cache:
            octavia_cache[region] = {}
        self.cache = octavia_cache[region]

    def quota_show(self, project_id):
        self._ensure_project_exists(project_id)
        quota = self.cache.get(project_id, {}).get("quota", [])
        for item in self.resource_dict:
            if item not in quota:
                quota[item] = None
        return {"quota": quota}

    def quota_set(self, project_id, json):
        self._ensure_project_exists(project_id)
        self.cache[project_id]["quota"] = json["quota"]

    def quota_defaults_show(self):
        return {
            "quota": {
                "load_balancer": 10,
                "listener": -1,
                "member": 50,
                "pool": -1,
                "health_monitor": -1,
            }
        }

    def lister(self, resource_type):
        def action(project_id=None):
            self._ensure_project_exists(project_id)
            resource = self.cache.get(project_id, {}).get(resource_type, [])
            links_name = resource_type + "_links"
            resource_name = self.resource_dict[resource_type]
            return {resource_name: resource, links_name: []}

        return action

    def _ensure_project_exists(self, project_id):
        if project_id not in self.cache:
            self.cache[project_id] = {name: [] for name in self.resource_dict.keys()}
            self.cache[project_id]["quota"] = dict(CONF.quota.sizes["small"]["octavia"])

    def __getattr__(self, name):
        # NOTE(amelia): This is out of pure laziness
        global octavia_cache
        if name[-5:] == "_list" and name[:-5] in self.resource_dict:
            return self.lister(name[:-5])
        else:
            raise AttributeError


class FakeTroveClient(object):
    class FakeTroveQuotaManager(object):

        FakeTroveResource = namedtuple(
            "FakeTroveResource", ["resource", "in_use", "reserved", "limit"]
        )

        def __init__(self, region):

            global trove_cache
            self.region = region
            if region not in trove_cache:
                trove_cache[region] = {}
            self.cache = trove_cache[region]

        def show(self, project_id):
            quota = self.cache[project_id]["quota"]

            quotas = []
            resources = self.cache[project_id]["quota"].keys()
            reserved = 0
            for resource in resources:
                in_use = len(self.cache[project_id][resource])
                quotas.append(
                    self.FakeTroveResource(resource, in_use, reserved, quota[resource])
                )
            return quotas

        def update(self, project_id, values):
            if project_id not in self.cache:
                self.cache[project_id] = {"quota": {}}
            self.cache[project_id]["quota"] = values

    def __init__(self, region):
        self.quota = self.FakeTroveQuotaManager(region)


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
        """Stub class to represent volumes and snapshots"""

        def __init__(self, region, cache_key):
            self.region = region
            self.key = cache_key

        def list(self, search_opts=None):
            if search_opts:
                project_id = search_opts["project_id"]
                global cinder_cache
                return cinder_cache[self.region][project_id][self.key]

    def __init__(self, region):
        global cinder_cache
        self.region = region
        self._cache = cinder_cache
        self.quotas = FakeOpenstackClient.Quotas(self)
        self.volumes = self.FakeResourceGroup(region, "volumes")
        self.volume_snapshots = self.FakeResourceGroup(region, "volume_snapshots")


class FakeResource(object):
    """Stub class to represent an individual instance of a volume or
    snapshot"""

    def __init__(self, size):
        self.size = size


def setup_trove_cache(region, project_id):
    global trove_cache
    if region not in trove_cache:
        trove_cache[region] = {}
    if project_id not in trove_cache[region]:
        trove_cache[region][project_id] = {}

    trove_cache[region][project_id] = {
        "instances": [],
        "backups": [],
        "volumes": [],
    }

    trove_cache[region][project_id]["quota"] = dict(CONF.quota.sizes["small"]["trove"])


def setup_neutron_cache(region, project_id):
    global neutron_cache
    if region not in neutron_cache:
        neutron_cache[region] = {"i": 0}
    else:
        neutron_cache[region]["i"] = 0
    if project_id not in neutron_cache[region]:
        neutron_cache[region][project_id] = {}

    neutron_cache[region][project_id] = {
        "networks": {},
        "subnets": {},
        "routers": {},
        "security_groups": {},
        "floatingips": {},
        "security_group_rules": {},
        "ports": {},
    }

    neutron_cache[region][project_id]["quota"] = dict(
        CONF.quota.sizes["small"]["neutron"]
    )


def setup_cinder_cache(region, project_id):
    global cinder_cache
    if region not in cinder_cache:
        cinder_cache[region] = {}
    if project_id not in cinder_cache[region]:
        cinder_cache[region][project_id] = {}

    cinder_cache[region][project_id] = {
        "volumes": [],
        "volume_snapshots": [],
    }

    cinder_cache[region][project_id]["quota"] = dict(
        CONF.quota.sizes["small"]["cinder"]
    )


def setup_nova_cache(region, project_id):
    global nova_cache
    if region not in nova_cache:
        nova_cache[region] = {}
    if project_id not in nova_cache[region]:
        nova_cache[region][project_id] = {}

    # Mocking the nova limits api
    nova_cache[region][project_id] = {
        "absolute": {
            "totalInstancesUsed": 0,
            "totalFloatingIpsUsed": 0,
            "totalRAMUsed": 0,
            "totalCoresUsed": 0,
            "totalSecurityGroupsUsed": 0,
        }
    }
    nova_cache[region][project_id]["quota"] = dict(CONF.quota.sizes["small"]["nova"])


def setup_quota_cache(region_name, project_id, size="small"):
    """Sets up the quota cache for a given region and project"""
    global cinder_cache

    if region_name not in cinder_cache:
        cinder_cache[region_name] = {}

    if project_id not in cinder_cache[region_name]:
        cinder_cache[region_name][project_id] = {"quota": {}}

    cinder_cache[region_name][project_id]["quota"] = dict(
        CONF.quota.sizes[size]["cinder"]
    )

    global nova_cache
    if region_name not in nova_cache:
        nova_cache[region_name] = {}

    if project_id not in nova_cache[region_name]:
        nova_cache[region_name][project_id] = {"quota": {}}

    nova_cache[region_name][project_id]["quota"] = dict(CONF.quota.sizes[size]["nova"])

    global neutron_cache
    if region_name not in neutron_cache:
        neutron_cache[region_name] = {}

    if project_id not in neutron_cache[region_name]:
        neutron_cache[region_name][project_id] = {"quota": {}}

    neutron_cache[region_name][project_id]["quota"] = dict(
        CONF.quota.sizes[size]["neutron"]
    )


def setup_mock_caches(region, project_id):
    setup_nova_cache(region, project_id)
    setup_cinder_cache(region, project_id)
    setup_neutron_cache(region, project_id)
    setup_trove_cache(region, project_id)
    client = FakeOctaviaClient(region)
    if project_id in octavia_cache[region]:
        del octavia_cache[region][project_id]
    client._ensure_project_exists(project_id)


def get_fake_neutron(region):
    return FakeNeutronClient(region)


def get_fake_novaclient(region):
    return FakeNovaClient(region)


def get_fake_cinderclient(region):
    global cinder_cache
    return FakeCinderClient(region)


def get_fake_octaviaclient(region):
    return FakeOctaviaClient(region)


def get_fake_troveclient(region):
    return FakeTroveClient(region)
