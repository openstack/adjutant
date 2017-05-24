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

from adjutant.actions.v1.base import BaseAction, ProjectMixin
from django.conf import settings
from adjutant.actions import openstack_clients, user_store
import six


class NewDefaultNetworkAction(BaseAction, ProjectMixin):
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

    def __init__(self, *args, **kwargs):
        super(NewDefaultNetworkAction, self).__init__(*args, **kwargs)

    def _validate_region(self):
        if not self.region:
            self.add_note('ERROR: No region given.')
            return False

        id_manager = user_store.IdentityManager()
        region = id_manager.get_region(self.region)
        if not region:
            self.add_note('ERROR: Region does not exist.')
            return False

        self.add_note('Region: %s exists.' % self.region)
        return True

    def _validate_defaults(self):
        defaults = self.settings.get(self.region, {})

        if not defaults:
            self.add_note('ERROR: No default settings for region %s.' %
                          self.region)
            return False
        return True

    def _validate_keystone_user(self):
        keystone_user = self.action.task.keystone_user
        if keystone_user.get('project_id') != self.project_id:
            self.add_note('Project id does not match keystone user project.')
            return False
        return True

    def _validate(self):
        self.action.valid = (
            self._validate_region() and
            self._validate_project_id() and
            self._validate_defaults() and
            self._validate_keystone_user()
        )
        self.action.save()

    def _create_network(self):
        neutron = openstack_clients.get_neutronclient(region=self.region)
        defaults = self.settings.get(self.region, {})

        if not self.get_cache('network_id'):
            try:
                network_body = {
                    "network": {
                        "name": defaults['network_name'],
                        'tenant_id': self.project_id,
                        "admin_state_up": True
                    }
                }
                network = neutron.create_network(body=network_body)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating network: %s" %
                    (e, defaults['network_name']))
                raise
            self.set_cache('network_id', network['network']['id'])
            self.add_note("Network %s created for project %s" %
                          (defaults['network_name'],
                           self.project_id))
        else:
            self.add_note("Network %s already created for project %s" %
                          (defaults['network_name'],
                           self.project_id))

        if not self.get_cache('subnet_id'):
            try:
                subnet_body = {
                    "subnet": {
                        "network_id": self.get_cache('network_id'),
                        "ip_version": 4,
                        'tenant_id': self.project_id,
                        'dns_nameservers': defaults['DNS_NAMESERVERS'],
                        "cidr": defaults['SUBNET_CIDR']
                    }
                }
                subnet = neutron.create_subnet(body=subnet_body)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating subnet" % e)
                raise
            self.set_cache('subnet_id', subnet['subnet']['id'])
            self.add_note("Subnet created for network %s" %
                          defaults['network_name'])
        else:
            self.add_note("Subnet already created for network %s" %
                          defaults['network_name'])

        if not self.get_cache('router_id'):
            try:
                router_body = {
                    "router": {
                        "name": defaults['router_name'],
                        "external_gateway_info": {
                            "network_id": defaults['public_network']
                        },
                        'tenant_id': self.project_id,
                        "admin_state_up": True
                    }
                }
                router = neutron.create_router(body=router_body)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating router: %s" %
                    (e, defaults['router_name']))
                raise
            self.set_cache('router_id', router['router']['id'])
            self.add_note("Router created for project %s" %
                          self.project_id)
        else:
            self.add_note("Router already created for project %s" %
                          self.project_id)

        if not self.get_cache('port_id'):
            try:
                interface_body = {
                    "subnet_id": self.get_cache('subnet_id')
                }
                interface = neutron.add_interface_router(
                    self.get_cache('router_id'), body=interface_body)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while attaching interface" % e)
                raise
            self.set_cache('port_id', interface['port_id'])
            self.add_note("Interface added to router for subnet")
        else:
            self.add_note(
                "Interface added to router for project %s" % self.project_id)

    def _pre_approve(self):
        # Note: Do we need to get this from cache? it is a required setting
        # self.project_id = self.action.task.cache.get('project_id', None)
        self._validate()

    def _post_approve(self):
        self._validate()

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
        # Note: Don't check project here as it doesn't exist yet.
        self.action.valid = (
            self._validate_region() and
            self._validate_defaults()
        )
        self.action.save()

    def _validate(self):
        self.action.valid = (
            self._validate_region() and
            self._validate_project_id() and
            self._validate_defaults()
        )
        self.action.save()

    def _pre_approve(self):
        self._pre_validate()

    def _post_approve(self):
        self.project_id = self.action.task.cache.get('project_id', None)
        self._validate()

        if self.setup_network and self.valid:
            self._create_network()


class SetProjectQuotaAction(BaseAction):
    """ Updates quota for a given project to a configured quota level """

    class ServiceQuotaFunctor(object):
        def __call__(self, project_id, values):
            self.client.quotas.update(project_id, **values)

    class ServiceQuotaCinderFunctor(ServiceQuotaFunctor):
        def __init__(self, region_name):
            self.client = openstack_clients.get_cinderclient(
                region=region_name)

    class ServiceQuotaNovaFunctor(ServiceQuotaFunctor):
        def __init__(self, region_name):
            self.client = openstack_clients.get_novaclient(
                region=region_name)

    class ServiceQuotaNeutronFunctor(ServiceQuotaFunctor):
        def __init__(self, region_name):
            self.client = openstack_clients.get_neutronclient(
                region=region_name)

        def __call__(self, project_id, values):
            body = {
                'quota': values
            }
            self.client.update_quota(project_id, body)

    _quota_updaters = {
        'cinder': ServiceQuotaCinderFunctor,
        'nova': ServiceQuotaNovaFunctor,
        'neutron': ServiceQuotaNeutronFunctor
    }

    def _validate_project_exists(self):
        if not self.project_id:
            self.add_note('No project_id set, previous action should have '
                          'set it.')
            return False

        id_manager = user_store.IdentityManager()
        project = id_manager.get_project(self.project_id)
        if not project:
            self.add_note('Project with id %s does not exist.' %
                          self.project_id)
            return False
        self.add_note('Project with id %s exists.' % self.project_id)
        return True

    def _pre_validate(self):
        # Nothing to validate yet.
        self.action.valid = True
        self.action.save()

    def _validate(self):
        # Make sure the project id is valid and can be used
        self.action.valid = (
            self._validate_project_exists()
        )
        self.action.save()

    def _pre_approve(self):
        self._pre_validate()

    def _post_approve(self):
        # Assumption: another action has placed the project_id into the cache.
        self.project_id = self.action.task.cache.get('project_id', None)
        self._validate()

        if not self.valid or self.action.state == "completed":
            return

        # update quota for each openstack service
        regions_dict = self.settings.get('regions', {})
        for region_name, region_settings in six.iteritems(regions_dict):
            quota_size = region_settings.get('quota_size')
            quota_settings = settings.PROJECT_QUOTA_SIZES.get(quota_size, {})
            if not quota_settings:
                self.add_note(
                    "Project quota not defined for size '%s' in region %s." % (
                        quota_size, region_name))
                continue
            for service_name, values in six.iteritems(quota_settings):
                updater_class = self._quota_updaters.get(service_name)
                if not updater_class:
                    self.add_note("No quota updater found for %s. Ignoring" %
                                  service_name)
                    continue
                # functor for the service+region
                service_functor = updater_class(region_name)
                service_functor(self.project_id, values)
            self.add_note(
                "Project quota for region %s set to %s" % (
                    region_name, quota_size))

        self.action.state = "completed"
        self.action.save()

    def _submit(self, token_data):
        pass
