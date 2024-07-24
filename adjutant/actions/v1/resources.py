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

from datetime import timedelta

from django.utils import timezone

from confspirator import groups
from confspirator import fields

from adjutant.actions.v1.base import BaseAction, ProjectMixin, QuotaMixin
from adjutant.actions.v1 import serializers
from adjutant.actions.utils import validate_steps
from adjutant.common import openstack_clients, user_store
from adjutant.api import models
from adjutant.common.quota import QuotaManager
from adjutant.config import CONF


class NewDefaultNetworkAction(BaseAction, ProjectMixin):
    """
    This action will setup all required basic networking
    resources so that a new user can launch instances
    right away.
    """

    required = [
        "setup_network",
        "project_id",
        "region",
    ]

    serializer = serializers.NewDefaultNetworkSerializer

    config_group = groups.DynamicNameConfigGroup(
        children=[
            groups.ConfigGroup(
                "region_defaults",
                children=[
                    fields.StrConfig(
                        "network_name",
                        help_text="Name to be given to the default network.",
                        default="default_network",
                    ),
                    fields.StrConfig(
                        "subnet_name",
                        help_text="Name to be given to the default subnet.",
                        default="default_subnet",
                    ),
                    fields.StrConfig(
                        "router_name",
                        help_text="Name to be given to the default router.",
                        default="default_router",
                    ),
                    fields.StrConfig(
                        "public_network",
                        help_text="ID of the public network.",
                    ),
                    fields.StrConfig(
                        "subnet_cidr",
                        help_text="CIDR for the default subnet.",
                    ),
                    fields.ListConfig(
                        "dns_nameservers",
                        help_text="DNS nameservers for the subnet.",
                    ),
                ],
            ),
            fields.DictConfig(
                "regions",
                help_text="Specific per region config for default network. "
                "See 'region_defaults'.",
                default={},
            ),
            fields.ListConfig(
                "create_in_regions",
                help_text=(
                    "Set the regions in which a default network will be "
                    "created. When unset or empty, the default behaviour "
                    "depends on the value of 'create_in_all_regions'."
                ),
                default=[],
                required=False,
            ),
            fields.BoolConfig(
                "create_in_all_regions",
                help_text=(
                    "When set to False (the default), if no regions are set "
                    "in 'create_in_regions', a default network will only be "
                    "created in the default region for new sign-ups. "
                    "When set to True, a default network will be created in "
                    "all regions, not just the default region."
                ),
                default=False,
                required=False,
            ),
        ]
    )

    def __init__(self, *args, **kwargs):
        super(NewDefaultNetworkAction, self).__init__(*args, **kwargs)

    def _validate_region(self):
        if not self.region:
            self.add_note("ERROR: No region given.")
            return False

        id_manager = user_store.IdentityManager()
        region = id_manager.get_region(self.region)
        if not region:
            self.add_note("ERROR: Region does not exist.")
            return False

        self.add_note("Region: %s exists." % self.region)
        return True

    def _validate(self):
        self.action.valid = validate_steps(
            [
                self._validate_region,
                self._validate_project_id,
                self._validate_keystone_user_project_id,
            ]
        )
        self.action.save()

    def _create_network(self):
        if self.config.create_in_regions:
            for region in self.config.create_in_regions:
                self._create_network_in_region(region)
        elif self.config.create_in_all_regions:
            id_manager = user_store.IdentityManager()
            for region in id_manager.list_regions():
                region_id = region.id
                self._create_network_in_region(region_id)
        else:
            self._create_network_in_region(self.region)

    def _create_network_in_region(self, region):
        neutron = openstack_clients.get_neutronclient(region=region)
        try:
            region_config = self.config.regions[region]
            network_config = self.config.region_defaults.overlay(region_config)
        except KeyError:
            network_config = self.config.region_defaults

        cache_suffix = f"_{region}"
        is_default_region = region == self.region

        network_id = self.get_cache(f"network_id{cache_suffix}")
        # NOTE(callumdickinson): Backwards compatibility with older tasks.
        if not network_id and is_default_region:
            network_id = self.get_cache("network_id")
        # If the default network does not exist, create it.
        if not network_id:
            try:
                network_body = {
                    "network": {
                        "name": network_config.network_name,
                        "tenant_id": self.project_id,
                        "admin_state_up": True,
                    }
                }
                network = neutron.create_network(body=network_body)
            except Exception as e:
                self.add_note(
                    (
                        f"Error while creating network '{network_config.network_name}' "
                        f"for project '{self.project_id}' in region '{region}': {e}"
                    ),
                )
                raise
            network_id = network["network"]["id"]
            self.add_note(
                (
                    f"Network '{network_config.network_name}' "
                    f"created for project '{self.project_id}' in region '{region}'"
                ),
            )
        else:
            self.add_note(
                (
                    f"Network '{network_config.network_name}' "
                    f"already created for project '{self.project_id}' "
                    f"in region '{region}'"
                ),
            )
        self.set_cache(f"network_id{cache_suffix}", network_id)

        subnet_id = self.get_cache(f"subnet_id{cache_suffix}")
        # NOTE(callumdickinson): Backwards compatibility with older tasks.
        if not subnet_id and is_default_region:
            subnet_id = self.get_cache("subnet_id")
        # If the default subnet does not exist, create it.
        if not subnet_id:
            try:
                subnet_body = {
                    "subnet": {
                        "network_id": network_id,
                        "ip_version": 4,
                        "tenant_id": self.project_id,
                        "dns_nameservers": network_config.dns_nameservers,
                        "cidr": network_config.subnet_cidr,
                    }
                }
                subnet = neutron.create_subnet(body=subnet_body)
            except Exception as e:
                self.add_note(
                    (
                        "Error while creating subnet "
                        f"in network '{network_config.network_name}' "
                        f"for project '{self.project_id}' in region '{region}': {e}"
                    ),
                )
                raise
            subnet_id = subnet["subnet"]["id"]
            self.add_note(
                (
                    f"Subnet '{subnet_id}' created "
                    f"in network '{network_config.network_name}' "
                    f"created for project '{self.project_id}' in region '{region}'"
                ),
            )
        else:
            self.add_note(
                (
                    f"Subnet '{subnet_id}' already created "
                    f"in network '{network_config.network_name}' "
                    f"created for project '{self.project_id}' in region '{region}'"
                ),
            )
        self.set_cache(f"subnet_id{cache_suffix}", subnet_id)

        router_id = self.get_cache(f"router_id{cache_suffix}")
        # NOTE(callumdickinson): Backwards compatibility with older tasks.
        if not router_id and is_default_region:
            router_id = self.get_cache("router_id")
        # If the default router does not exist, create it.
        if not router_id:
            try:
                router_body = {
                    "router": {
                        "name": network_config.router_name,
                        "external_gateway_info": {
                            "network_id": network_config.public_network
                        },
                        "tenant_id": self.project_id,
                        "admin_state_up": True,
                    }
                }
                router = neutron.create_router(body=router_body)
            except Exception as e:
                self.add_note(
                    (
                        f"Error while creating router '{network_config.router_name}' "
                        f"for project '{self.project_id}' in region '{region}': {e}"
                    ),
                )
                raise
            router_id = router["router"]["id"]
            self.add_note(
                (
                    f"Router '{network_config.router_name}' "
                    f"created for project '{self.project_id}' in region '{region}'"
                ),
            )
        else:
            self.add_note(
                (
                    f"Router '{network_config.router_name}' "
                    f"already created for project '{self.project_id}' "
                    f"in region '{region}'"
                ),
            )
        self.set_cache(f"router_id{cache_suffix}", router_id)

        port_id = self.get_cache(f"port_id{cache_suffix}")
        # NOTE(callumdickinson): Backwards compatibility with older tasks.
        if not port_id and is_default_region:
            port_id = self.get_cache("port_id")
        # If the subnet port on the default router does not exist, create it.
        if not port_id:
            try:
                interface_body = {"subnet_id": subnet_id}
                interface = neutron.add_interface_router(router_id, body=interface_body)
            except Exception as e:
                self.add_note(
                    (
                        "Error while adding interface "
                        f"for network '{network_config.network_name}' "
                        f"to router '{network_config.router_name}' "
                        f"for project '{self.project_id}' "
                        f"in region '{region}': {e}"
                    ),
                )
                raise
            port_id = interface["port_id"]
            self.add_note(
                (
                    f"Interface '{interface['port_id']}' "
                    f"for network '{network_config.network_name}' "
                    f"added to router '{network_config.router_name}' "
                    f"for project '{self.project_id}' "
                    f"in region '{region}'"
                ),
            )
        else:
            self.add_note(
                (
                    f"Interface '{port_id}' "
                    f"for network '{network_config.network_name}' "
                    f"already added to router '{network_config.router_name}' "
                    f"for project '{self.project_id}' "
                    f"in region '{region}'"
                ),
            )
        self.set_cache(f"port_id{cache_suffix}", port_id)

    def _prepare(self):
        # Note: Do we need to get this from cache? it is a required setting
        # self.project_id = self.action.task.cache.get('project_id', None)
        self._validate()

    def _approve(self):
        self._validate()

        if self.setup_network and self.valid:
            self._create_network()

    def _submit(self, token_data, keystone_user=None):
        pass


class NewProjectDefaultNetworkAction(NewDefaultNetworkAction):
    """
    A variant of NewDefaultNetwork that expects the project
    to not be created until after approve.
    """

    required = [
        "setup_network",
        "region",
    ]

    serializer = serializers.NewProjectDefaultNetworkSerializer

    def _pre_validate(self):
        # Note: Don't check project here as it doesn't exist yet.
        self.action.valid = validate_steps(
            [
                self._validate_region,
            ]
        )
        self.action.save()

    def _validate(self):
        self.action.valid = validate_steps(
            [
                self._validate_region,
                self._validate_project_id,
            ]
        )
        self.action.save()

    def _prepare(self):
        self._pre_validate()

    def _approve(self):
        self.project_id = self.action.task.cache.get("project_id", None)
        self._validate()

        if self.setup_network and self.valid:
            self._create_network()


class UpdateProjectQuotasAction(BaseAction, QuotaMixin):
    """Updates quota for a project to a given size in a list of regions"""

    required = [
        "size",
        "project_id",
        "regions",
    ]

    serializer = serializers.UpdateProjectQuotasSerializer

    config_group = groups.DynamicNameConfigGroup(
        children=[
            fields.FloatConfig(
                "size_difference_threshold",
                help_text="Precentage different allowed when matching quota sizes.",
                default=0.1,
                min=0,
                max=1,
            ),
            fields.IntConfig(
                "days_between_autoapprove",
                help_text="The allowed number of days between auto approved quota changes.",
                default=30,
            ),
        ]
    )

    def _get_email(self):
        if CONF.identity.username_is_email:
            return self.action.task.keystone_user["username"]
        else:
            id_manager = user_store.IdentityManager()
            user = id_manager.get_user(self.action.task.keystone_user["user_id"])
            email = getattr(user, "email", None)
            if email:
                return email

        self.add_note("User email address not set.")
        return None

    def _validate_quota_size_exists(self):
        size_list = CONF.quota.sizes.keys()
        if self.size not in size_list:
            self.add_note("Quota size: %s does not exist" % self.size)
            return False
        return True

    def _validate_quota_management_enabled_for_regions(self):
        # Check that at least one region in the given list has
        # quota management enabled.
        default_services = CONF.quota.services.get("*", {})
        for region in self.regions:
            if CONF.quota.services.get(region, default_services):
                return True
        self.add_note(
            "Quota management is disabled for all specified regions",
        )
        return False

    def _set_region_quota(self, region_name, quota_size):
        # Set the quota for an individual region
        quota_config = CONF.quota.sizes.get(quota_size, {})
        if not quota_config:
            self.add_note(
                "Project quota not defined for size '%s' in region %s."
                % (quota_size, region_name)
            )
            return

        quota_manager = QuotaManager(
            self.project_id, self.config.size_difference_threshold
        )

        quota_manager.set_region_quota(region_name, quota_config)

        self.add_note(
            "Project quota for region %s set to %s" % (region_name, quota_size)
        )

    def _can_auto_approve(self):
        wait_days = self.config.days_between_autoapprove
        task_list = models.Task.objects.filter(
            completed_on__gte=timezone.now() - timedelta(days=wait_days),
            task_type__exact=self.action.task.task_type,
            cancelled__exact=False,
            project_id__exact=self.project_id,
        )

        changed_in_period = False
        # Check to see if there have been any updates in the relavent regions
        # recently
        for task in task_list:
            for action in task.actions:
                intersect = set(action.action_data["regions"]).intersection(
                    self.regions
                )
                if intersect:
                    changed_in_period = True

        region_sizes = []

        quota_manager = QuotaManager(
            self.project_id, self.config.size_difference_threshold
        )

        for region in self.regions:
            current_quota = quota_manager.get_region_quota_data(
                region, include_usage=False
            )
            # If get_region_quota_data returns None, this region
            # has quota management disabled.
            if not current_quota:
                self.add_note(
                    f"Quota management is disabled in region: {region}",
                )
                continue
            current_size = current_quota["current_quota_size"]
            region_sizes.append(current_size)
            self.add_note(
                "Project has size '%s' in region: '%s'" % (current_size, region)
            )

        # Check for preapproved_quotas
        preapproved_quotas = []
        smaller_quotas = []

        if not region_sizes:
            self.add_note(
                "Quota management is disabled for all specified regions",
            )
            return False

        # If all region sizes are the same
        if region_sizes.count(region_sizes[0]) == len(region_sizes):
            preapproved_quotas = quota_manager.get_quota_change_options(region_sizes[0])
            smaller_quotas = quota_manager.get_smaller_quota_options(region_sizes[0])

        if self.size in smaller_quotas:
            self.add_note(
                "Quota size '%s' is in list of smaller quotas: %s"
                % (self.size, smaller_quotas)
            )
            return True

        if changed_in_period:
            self.add_note(
                "Quota has already been updated within the auto " "approve time limit."
            )
            return False

        if self.size not in preapproved_quotas:
            self.add_note(
                "Quota size '%s' not in preapproved list: %s"
                % (self.size, preapproved_quotas)
            )
            return False

        self.add_note(
            "Quota size '%s' in preapproved list: %s" % (self.size, preapproved_quotas)
        )
        return True

    def _validate(self):
        # Make sure the project id is valid and can be used
        self.action.valid = validate_steps(
            [
                self._validate_project_id,
                self._validate_quota_size_exists,
                self._validate_regions_exist,
                self._validate_quota_management_enabled_for_regions,
                self._validate_usage_lower_than_quota,
            ]
        )
        self.action.save()

    def _prepare(self):
        self._validate()
        # Set auto-approval
        self.set_auto_approve(self._can_auto_approve())

    def _approve(self):
        self._validate()

        if not self.valid or self.action.state == "completed":
            return

        # Use manager here instead, it will make it easier to add has_more
        # in later
        for region in self.regions:
            self._set_region_quota(region, self.size)

        self.action.state = "completed"
        self.action.task.cache["project_id"] = self.project_id
        self.action.task.cache["size"] = self.size

        self.action.save()

    def _submit(self, token_data, keystone_user=None):
        """
        Nothing to do here. Everything is done at approve.
        """
        pass


class SetProjectQuotaAction(UpdateProjectQuotasAction):
    """Updates quota for a given project to a configured quota level"""

    required = []

    serializer = serializers.SetProjectQuotaSerializer

    config_group = UpdateProjectQuotasAction.config_group.extend(
        children=[
            fields.DictConfig(
                "region_sizes",
                help_text="Which quota size to use for which region.",
                default={},
                sample_default={"RegionOne": "small"},
            ),
        ]
    )

    def _get_email(self):
        return None

    def _validate(self):
        # Make sure the project id is valid and can be used
        self.action.valid = validate_steps(
            [
                self._validate_project_id,
            ]
        )
        self.action.save()

    def _prepare(self):
        # Nothing to validate yet
        self.action.valid = True
        self.action.save()

    def _approve(self):
        # Assumption: another action has placed the project_id into the cache.
        self.project_id = self.action.task.cache.get("project_id", None)
        self._validate()

        if not self.valid or self.action.state == "completed":
            return

        # update quota for each openstack service
        for region_name, region_size in self.config.region_sizes.items():
            self._set_region_quota(region_name, region_size)

        self.action.state = "completed"
        self.action.save()

    def _submit(self, token_data, keystone_user=None):
        pass
