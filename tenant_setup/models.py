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

    # TODO(Adriant): work our more sensible defaults and how to deal
    # with multiple regions (defaults in settings file now).
    defaults = settings.NETWORK_DEFAULTS[settings.DEFAULT_REGION]

    def _validate(self):

        project_id = self.action.registration.cache.get('project_id', None)
        if project_id:
            self.action.valid = True
            self.action.need_token = False
            self.action.save()
            self.add_note('project_id given: %s' % project_id)
        self.add_note('No project_id given.')

    def _setup_resources(self):
        neutron = openstack_clients.get_neutronclient()

        project_id = self.action.registration.cache['project_id']

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
            raise e
        self.add_note("Network %s created for project %s" %
                      (self.defaults['network_name'],
                       self.action.registration.cache['project_id']))

        try:
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
        except Exception as e:
            self.add_note(
                "Error: '%s' while creating subnet" % e)
            raise e
        self.add_note("Subnet created for network %s" %
                      self.defaults['network_name'])

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
            raise e
        self.add_note("Router created for project %s" %
                      self.action.registration.cache['project_id'])

        try:
            interface_body = {
                "subnet_id": subnet['subnet']['id']
            }
            neutron.add_interface_router(router['router']['id'],
                                         body=interface_body)
        except Exception as e:
            self.add_note(
                "Error: '%s' while attaching interface" % e)
            raise e
        self.add_note("Interface added to router for subnet")

    def _pre_approve(self):
        if self.setup_resources:
            self._validate()

    def _post_approve(self):
        self._validate()
        if self.setup_resources and self.valid:
            self._setup_resources()

    def _submit(self, token_data):
        pass


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
            self.add_note('project_id given: %s' % project_id)
        self.add_note('No project_id given.')

    def _pre_approve(self):
        pass

    def _post_approve(self):
        self._validate()
        if self.valid:
            id_manager = IdentityManager()

            project = id_manager.get_project(
                self.action.registration.cache['project_id'])
            try:
                user = id_manager.find_user(name="admin")
                role = id_manager.find_role(name="admin")
                id_manager.add_user_role(user, role, project.id)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while adding admin to project: %s" %
                    (e, project.id))
                raise e
            self.add_note(
                'Admin has been added to %s.' %
                self.action.registration.cache['project_id'])

    def _submit(self, token_data):
        pass


action_classes = {
    'DefaultProjectResources': (DefaultProjectResources,
                                DefaultProjectResourcesSerializer),
    'AddAdminToProject': (AddAdminToProject, None)
}


settings.ACTION_CLASSES.update(action_classes)
