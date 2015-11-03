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
from stacktask.actions.tenant_setup.serializers import DefaultProjectResourcesSerializer
from django.conf import settings
from stacktask.actions.user_store import IdentityManager
from stacktask.actions import openstack_clients


class DefaultProjectResources(BaseAction):
    """
    This action will setup all required basic networking
    resources so that a new user can launch instances
    right away.
    """

    required = [
        'setup_resources'
    ]

    region = settings.DEFAULT_REGION

    defaults = settings.ACTION_SETTINGS['DefaultProjectResources'][region]

    def _validate(self):

        project_id = self.action.task.cache.get('project_id', None)

        valid = False
        if project_id:
            valid = True
            self.add_note('project_id given: %s' % project_id)
        else:
            self.add_note('No project_id given.')
        return valid

    def _setup_resources(self):
        neutron = openstack_clients.get_neutronclient()

        project_id = self.action.task.cache['project_id']

        if not self.get_cache('network_id'):
            try:
                network_body = {
                    "network": {
                        "name": self.defaults['network_name'],
                        'tenant_id': project_id,
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
                           self.action.task.cache['project_id']))
        else:
            self.add_note("Network %s already created for project %s" %
                          (self.defaults['network_name'],
                           self.action.task.cache['project_id']))

        if not self.get_cache('subnet_id'):
            try:
                subnet_body = {
                    "subnet": {
                        "network_id": self.get_cache('network_id'),
                        "ip_version": 4,
                        'tenant_id': project_id,
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
                        'tenant_id': project_id,
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
                          self.action.task.cache['project_id'])
        else:
            self.add_note("Router already created for project %s" %
                          self.action.task.cache['project_id'])

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
        # Not exactly valid, but not exactly invalid.
        self.action.valid = True
        self.action.save()

    def _post_approve(self):
        self.action.valid = self._validate()
        self.action.save()

        if self.setup_resources and self.valid:
            self._setup_resources()

    def _submit(self, token_data):
        pass


class AddAdminToProject(BaseAction):
    """
    Action to add 'admin' user to project for
    monitoring purposes.
    """

    def _validate(self):

        project_id = self.action.task.cache.get('project_id', None)

        valid = False
        if project_id:
            valid = True
            self.add_note('project_id given: %s' % project_id)
        else:
            self.add_note('No project_id given.')
        return valid

    def _pre_approve(self):
        # Not yet exactly valid, but not exactly invalid.
        self.action.valid = True
        self.action.save()

    def _post_approve(self):
        self.action.valid = self._validate()
        self.action.save()

        if self.valid and not self.action.state == "completed":
            id_manager = IdentityManager()

            project = id_manager.get_project(
                self.action.task.cache['project_id'])
            try:
                user = id_manager.find_user(name="admin")
                role = id_manager.find_role(name="admin")
                id_manager.add_user_role(user, role, project.id)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while adding admin to project: %s" %
                    (e, project.id))
                raise
            self.action.state = "completed"
            self.action.save()
            self.add_note(
                'Admin has been added to %s.' %
                self.action.task.cache['project_id'])

    def _submit(self, token_data):
        pass


action_classes = {
    'DefaultProjectResources': (DefaultProjectResources,
                                DefaultProjectResourcesSerializer),
    'AddAdminToProject': (AddAdminToProject, None)
}


settings.ACTION_CLASSES.update(action_classes)
