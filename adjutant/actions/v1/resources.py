#  Copyright (C) 2015 Catalyst IT Ltd
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

from adjutant.actions.v1.base import BaseAction, ProjectMixin, QuotaMixin
from adjutant.actions.utils import validate_steps
from adjutant.common import openstack_clients, user_store
from adjutant.api import models
from adjutant.common.quota import QuotaManager

from django.utils import timezone
from django.conf import settings

from datetime import timedelta


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
        self.action.valid = validate_steps([
            self._validate_region,
            self._validate_project_id,
            self._validate_defaults,
            self._validate_keystone_user,
        ])
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
        self.action.valid = validate_steps([
            self._validate_region,
            self._validate_defaults,
        ])
        self.action.save()

    def _validate(self):
        self.action.valid = validate_steps([
            self._validate_region,
            self._validate_project_id,
            self._validate_defaults,
        ])
        self.action.save()

    def _pre_approve(self):
        self._pre_validate()

    def _post_approve(self):
        self.project_id = self.action.task.cache.get('project_id', None)
        self._validate()

        if self.setup_network and self.valid:
            self._create_network()


class UpdateProjectQuotasAction(BaseAction, QuotaMixin):
    """ Updates quota for a project to a given size in a list of regions """

    required = [
        'size',
        'project_id',
        'regions',
    ]

    default_days_between_autoapprove = 30

    def __init__(self, *args, **kwargs):
        super(UpdateProjectQuotasAction, self).__init__(*args, **kwargs)
        self.size_difference_threshold = settings.TASK_SETTINGS.get(
            self.action.task.task_type, {}).get(
            'size_difference_threshold')

    def _get_email(self):

        if settings.USERNAME_IS_EMAIL:
            return self.action.task.keystone_user['username']
        else:
            id_manager = user_store.IdentityManager()
            user = id_manager.users.get(self.keystone_user['user_id'])
            email = user.email
            if email:
                return email

        self.add_note("User email address not set.")
        return None

    def _validate_quota_size_exists(self):
        size_list = settings.PROJECT_QUOTA_SIZES.keys()
        if self.size not in size_list:
            self.add_note("Quota size: %s does not exist" % self.size)
            return False
        return True

    def _set_region_quota(self, region_name, quota_size):
        # Set the quota for an individual region
        quota_settings = settings.PROJECT_QUOTA_SIZES.get(quota_size, {})
        if not quota_settings:
            self.add_note(
                "Project quota not defined for size '%s' in region %s." % (
                    quota_size, region_name))
            return

        quota_manager = QuotaManager(self.project_id,
                                     self.size_difference_threshold)

        quota_manager.set_region_quota(region_name, quota_settings)

        self.add_note("Project quota for region %s set to %s" % (
                      region_name, quota_size))

    def _can_auto_approve(self):
        wait_days = self.settings.get('days_between_autoapprove',
                                      self.default_days_between_autoapprove)
        task_list = models.Task.objects.filter(
            completed_on__gte=timezone.now() - timedelta(days=wait_days),
            task_type__exact=self.action.task.task_type,
            cancelled__exact=False,
            project_id__exact=self.project_id)

        changed_in_period = False
        # Check to see if there have been any updates in the relavent regions
        # recently
        for task in task_list:
            for action in task.actions:
                intersect = set(action.action_data[
                    'regions']).intersection(self.regions)
                if intersect:
                    changed_in_period = True

        region_sizes = []

        quota_manager = QuotaManager(self.project_id,
                                     self.size_difference_threshold)

        for region in self.regions:
            current_size = quota_manager.get_region_quota_data(
                region, include_usage=False)['current_quota_size']
            region_sizes.append(current_size)
            self.add_note(
                "Project has size '%s' in region: '%s'" %
                (current_size, region))

        # Check for preapproved_quotas
        preapproved_quotas = []
        smaller_quotas = []

        # If all region sizes are the same
        if region_sizes.count(region_sizes[0]) == len(region_sizes):
            preapproved_quotas = quota_manager.get_quota_change_options(
                region_sizes[0])
            smaller_quotas = quota_manager.get_smaller_quota_options(
                region_sizes[0])

        if self.size in smaller_quotas:
            self.add_note(
                "Quota size '%s' is in list of smaller quotas: %s" %
                (self.size, smaller_quotas))
            return True

        if changed_in_period:
            self.add_note(
                "Quota has already been updated within the auto "
                "approve time limit.")
            return False

        if self.size not in preapproved_quotas:
            self.add_note(
                "Quota size '%s' not in preapproved list: %s" %
                (self.size, preapproved_quotas))
            return False

        self.add_note(
            "Quota size '%s' in preapproved list: %s" %
            (self.size, preapproved_quotas))
        return True

    def _validate(self):
        # Make sure the project id is valid and can be used
        self.action.valid = validate_steps([
            self._validate_project_id,
            self._validate_quota_size_exists,
            self._validate_regions_exist,
            self._validate_usage_lower_than_quota,
        ])
        self.action.save()

    def _pre_approve(self):
        self._validate()
        # Set auto-approval
        self.set_auto_approve(self._can_auto_approve())

    def _post_approve(self):
        self._validate()

        if not self.valid or self.action.state == "completed":
            return

        # Use manager here instead, it will make it easier to add has_more
        # in later
        for region in self.regions:
            self._set_region_quota(region, self.size)

        self.action.state = "completed"
        self.action.task.cache['project_id'] = self.project_id
        self.action.task.cache['size'] = self.size

        self.action.save()

    def _submit(self, token_data):
        """
        Nothing to do here. Everything is done at post_approve.
        """
        pass


class SetProjectQuotaAction(UpdateProjectQuotasAction):
    """ Updates quota for a given project to a configured quota level """
    required = []

    def _get_email(self):
        return None

    def _validate(self):
        # Make sure the project id is valid and can be used
        self.action.valid = validate_steps([
            self._validate_project_id,
        ])
        self.action.save()

    def _pre_approve(self):
        # Nothing to validate yet
        self.action.valid = True
        self.action.save()

    def _post_approve(self):
        # Assumption: another action has placed the project_id into the cache.
        self.project_id = self.action.task.cache.get('project_id', None)
        self._validate()

        if not self.valid or self.action.state == "completed":
            return

        # update quota for each openstack service
        regions_dict = self.settings.get('regions', {})
        for region_name, region_settings in regions_dict.items():
            quota_size = region_settings.get('quota_size')
            self._set_region_quota(region_name, quota_size)

        self.action.state = "completed"
        self.action.save()

    def _submit(self, token_data):
        pass
