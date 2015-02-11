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

from base.models import BaseAction
from serializers import DefaultProjectResourcesSerializer
from django.conf import settings
from base.user_store import IdentityManager
from base import openstack_clients


class DefaultProjectResources(BaseAction):
    """This action will setup all required basic networking
       resources so that a new user can launch instances
       right away."""

    required = [
        'setup_resources'
    ]

    # TODO(Adriant): Ideally move these to the settings file
    defaults = {
        'network_name': 'somenetwork',
        'subnet_name': 'somesubnet',
        'router_name': 'somerouter',
        # this depends on region and needs to be pulled from somewhere:
        'public_network': 'aed4df5a-1a1f-42e4-b105-aa7f2edc7a95',
        'DNS_NAMESERVERS': ['193.168.1.2',
                            '193.168.1.3'],
        'SUBNET_CIDR': '192.168.1.0/24'
    }

    def _validate(self):

        project_id = self.action.registration.cache.get('project_id', None)
        # need to check, does tenant exist.
        if project_id:
            self.action.valid = True
            self.action.need_token = False
            self.action.save()
            return ['project_id given: %s' % project_id]
        return ['No project_id given.']

    def _setup_resources(self):
        neutron = openstack_clients.get_neutronclient()

        notes = []

        project_id = self.action.registration.cache['project_id']

        # TODO(Adriant): Setup proper exception handling
        # and error logging so we know where it died.

        network_body = {
            "network": {
                "name": self.defaults['network_name'],
                'tenant_id': project_id,
                "admin_state_up": True
            }
        }
        network = neutron.create_network(body=network_body)
        notes.append("Network %s created for project %s" %
                     (self.defaults['network_name'],
                      self.action.registration.cache['project_id']))

        subnet_body = {
            "subnet": {
                "network_id": network['network']['id'],
                "ip_version": 4,
                'tenant_id': project_id,
                'dns_nameservers': self.defaults['DNS_NAMESERVERS'],
                "cidr": self.defaults['SUBNET_CIDR']
            }
        }
        subnet = neutron.create_subnet(body=subnet_body)
        notes.append("Subnet created for network %s" %
                     self.defaults['network_name'])

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
        notes.append("Router created for project %s" %
                     self.action.registration.cache['project_id'])

        interface_body = {
            "subnet_id": subnet['subnet']['id']
        }
        neutron.add_interface_router(router['router']['id'],
                                     body=interface_body)
        notes.append("Interface added to router for subnet")

        return notes

    def _pre_approve(self):
        if self.setup_resources:
            return self._validate()
        return []

    def _post_approve(self):
        self._validate()
        if self.setup_resources and self.valid:
            return self._setup_resources()
        return []

    def _submit(self, token_data):
        return []


class AddAdminToProject(BaseAction):
    """Action to add 'admin' user to project for
       monitoring purposes."""

    def _validate(self):

        project_id = self.action.registration.cache.get('project_id', None)
        # need to check, does tenant exist.
        if project_id:
            self.action.valid = True
            self.action.need_token = False
            self.action.save()
            return ['project_id given: %s' % project_id]
        return ['No project_id given.']

    def _pre_approve(self):
        return []

    def _post_approve(self):
        notes = self._validate()
        if self.valid:
            id_manager = IdentityManager()

            project = id_manager.get_project(
                self.action.registration.cache['project_id'])
            user = id_manager.find_user(name="admin")
            role = id_manager.find_role(name="admin")
            id_manager.add_user_role(user, role, project.id)
            notes.append(
                'Admin has been added to %s.' %
                self.action.registration.cache['project_id'])
            return notes
        return notes

    def _submit(self, token_data):
        return []


action_classes = {
    'DefaultProjectResources': (DefaultProjectResources,
                                DefaultProjectResourcesSerializer),
    'AddAdminToProject': (AddAdminToProject, None)
}


settings.ACTION_CLASSES.update(action_classes)
