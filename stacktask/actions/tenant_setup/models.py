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

from stacktask.actions.models import BaseAction
from stacktask.actions.tenant_setup import serializers
from django.conf import settings
from stacktask.actions.user_store import IdentityManager
from stacktask.actions import openstack_clients


class NewDefaultNetworkAction(BaseAction):
    """
    This action will setup all required basic networking
    resources so that a new user can launch instances
    right away.
    """

    required = [
        'setup_network',
        'project_id',
        'region',
    ]

    def _validate(self):

        # Default state is invalid
        self.action.valid = False

        if not self.project_id:
            self.add_note('No project_id given.')
            return

        if not self.region:
            self.add_note('No region given.')
            return

        keystone_user = self.action.task.keystone_user
        if keystone_user.get('project_id') != self.project_id:
            self.add_note('Project id does not match keystone user project.')
            return

        id_manager = IdentityManager()

        project = id_manager.get_project(self.project_id)
        if not project:
            self.add_note('Project does not exist.')
            return
        self.add_note('Project_id: %s exists.' % project.id)

        region = id_manager.find_region(self.region)
        if not region:
            self.add_note('Region does not exist.')
            return
        self.add_note('Region: %s exists.' % self.region)

        self.defaults = settings.ACTION_SETTINGS.get(
            'NewDefaultNetworkAction', {}).get(self.region, {})

        if not self.defaults:
            self.add_note('ERROR: No default settings for given region.')
            return

        self.action.valid = True

    def _create_network(self):

        neutron = openstack_clients.get_neutronclient(region=self.region)

        if not self.get_cache('network_id'):
            try:
                network_body = {
                    "network": {
                        "name": self.defaults['network_name'],
                        'tenant_id': self.project_id,
                        "admin_state_up": True
                    }
                }
                network = neutron.create_network(body=network_body)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating network: %s" %
                    (e, self.defaults['network_name']))
                raise
            self.set_cache('network_id', network['network']['id'])
            self.add_note("Network %s created for project %s" %
                          (self.defaults['network_name'],
                           self.project_id))
        else:
            self.add_note("Network %s already created for project %s" %
                          (self.defaults['network_name'],
                           self.project_id))

        if not self.get_cache('subnet_id'):
            try:
                subnet_body = {
                    "subnet": {
                        "network_id": self.get_cache('network_id'),
                        "ip_version": 4,
                        'tenant_id': self.project_id,
                        'dns_nameservers': self.defaults['DNS_NAMESERVERS'],
                        "cidr": self.defaults['SUBNET_CIDR']
                    }
                }
                subnet = neutron.create_subnet(body=subnet_body)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating subnet" % e)
                raise
            self.set_cache('subnet_id', subnet['subnet']['id'])
            self.add_note("Subnet created for network %s" %
                          self.defaults['network_name'])
        else:
            self.add_note("Subnet already created for network %s" %
                          self.defaults['network_name'])

        if not self.get_cache('router_id'):
            try:
                router_body = {
                    "router": {
                        "name": self.defaults['router_name'],
                        "external_gateway_info": {
                            "network_id": self.defaults['public_network']
                        },
                        'tenant_id': self.project_id,
                        "admin_state_up": True
                    }
                }
                router = neutron.create_router(body=router_body)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating router: %s" %
                    (e, self.defaults['router_name']))
                raise
            self.set_cache('router_id', router['router']['id'])
            self.add_note("Router created for project %s" %
                          self.project_id)
        else:
            self.add_note("Router already created for project %s" %
                          self.project_id)

        try:
            interface_body = {
                "subnet_id": self.get_cache('subnet_id')
            }
            neutron.add_interface_router(self.get_cache('router_id'),
                                         body=interface_body)
        except Exception as e:
            self.add_note(
                "Error: '%s' while attaching interface" % e)
            raise
        self.add_note("Interface added to router for subnet")

    def _pre_approve(self):
        self._validate()
        self.action.save()

    def _post_approve(self):
        self._validate()
        self.action.save()

        if self.setup_network and self.valid:
            self._create_network()

    def _submit(self, token_data):
        pass


class NewProjectDefaultNetworkAction(NewDefaultNetworkAction):
    """
    A variant of NewDefaultNetwork that expects the project
    to not be created until after post_approve.
    """

    required = [
        'setup_network',
        'region',
    ]

    def _pre_validate(self):

        # Default state is invalid
        self.action.valid = False

        # We don't check project here as it doesn't exist yet.

        if not self.region:
            self.add_note('No region given.')
            return

        id_manager = IdentityManager()

        region = id_manager.find_region(self.region)
        if not region:
            self.add_note('Region does not exist.')
            return
        self.add_note('Region: %s exists.' % self.region)

        self.defaults = settings.ACTION_SETTINGS.get(
            'NewDefaultNetworkAction', {}).get(self.region, {})

        if not self.defaults:
            self.add_note('ERROR: No default settings for given region.')
            return

        self.action.valid = True

    def _validate(self):

        # Default state is invalid
        self.action.valid = False

        self.project_id = self.action.task.cache.get('project_id', None)

        if not self.project_id:
            self.add_note('No project_id given.')
            return

        if not self.region:
            self.add_note('No region given.')
            return

        id_manager = IdentityManager()

        project = id_manager.get_project(self.project_id)
        if not project:
            self.add_note('Project does not exist.')
            return
        self.add_note('Project_id: %s exists.' % project.id)

        region = id_manager.find_region(self.region)
        if not region:
            self.add_note('Region does not exist.')
            return
        self.add_note('Region: %s exists.' % self.region)

        self.defaults = settings.ACTION_SETTINGS.get(
            'NewDefaultNetworkAction', {}).get(self.region, {})

        if not self.defaults:
            self.add_note('ERROR: No default settings for given region.')
            return

        self.action.valid = True

    def _pre_approve(self):
        self._pre_validate()
        self.action.save()

    def _post_approve(self):
        self._validate()
        self.action.save()

        if self.setup_network and self.valid:
            self._create_network()


class AddDefaultUsersToProjectAction(BaseAction):
    """
    The purpose of this action is to add a given set of users after
    the creation of a new Project. This is mainly for administrative
    purposes, and for users involved with migrations, monitoring, and
    general admin tasks that should be present by default.
    """

    def _validate_users(self):
        self.users = settings.ACTION_SETTINGS.get(
            'AddDefaultUsersToProjectAction', {}).get('default_users', [])
        self.roles = settings.ACTION_SETTINGS.get(
            'AddDefaultUsersToProjectAction', {}).get('default_roles', [])

        id_manager = IdentityManager()

        all_found = True
        for user in self.users:
            ks_user = id_manager.find_user(user)
            if ks_user:
                self.add_note('User: %s exists.' % user)
            else:
                self.add_note('ERROR: User: %s does not exist.' % user)
                all_found = False

        for role in self.roles:
            ks_role = id_manager.find_role(role)
            if ks_role:
                self.add_note('Role: %s exists.' % role)
            else:
                self.add_note('ERROR: Role: %s does not exist.' % role)
                all_found = False

        if all_found:
            return True
        else:
            return False

    def _validate_project(self):
        self.project_id = self.action.task.cache.get('project_id', None)

        id_manager = IdentityManager()

        project = id_manager.get_project(self.project_id)
        if not project:
            self.add_note('Project does not exist.')
            return False
        self.add_note('Project_id: %s exists.' % project.id)
        return True

    def _validate(self):
        self.action.valid = self._validate_users() and self._validate_project()
        self.action.save()

    def _pre_approve(self):
        self.action.valid = self._validate_users()
        self.action.save()

    def _post_approve(self):
        self._validate()

        if self.valid and not self.action.state == "completed":
            id_manager = IdentityManager()

            project = id_manager.get_project(self.project_id)
            try:
                for user in self.users:
                    ks_user = id_manager.find_user(name=user)
                    for role in self.roles:
                        ks_role = id_manager.find_role(name=role)
                        id_manager.add_user_role(ks_user, ks_role, project.id)
                        self.add_note(
                            'User: "%s" given role: %s on project: %s.' %
                            (ks_user.name, ks_role.name, project.id))
            except Exception as e:
                self.add_note(
                    "Error: '%s' while adding users to project: %s" %
                    (e, project.id))
                raise
            self.action.state = "completed"
            self.action.save()
            self.add_note("All users added.")

    def _submit(self, token_data):
        pass


action_classes = {
    'NewDefaultNetworkAction':
        (NewDefaultNetworkAction,
         serializers.NewDefaultNetworkSerializer),
    'NewProjectDefaultNetworkAction':
        (NewProjectDefaultNetworkAction,
         serializers.NewProjectDefaultNetworkSerializer),
    'AddDefaultUsersToProjectAction':
        (AddDefaultUsersToProjectAction,
         serializers.AddDefaultUsersToProjectSerializer)
}

settings.ACTION_CLASSES.update(action_classes)
