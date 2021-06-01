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

from adjutant.config import CONF
from adjutant.common import openstack_clients


class QuotaManager(object):
    """
    A manager to allow easier updating and access to quota information
    across all services.
    """

    default_size_diff_threshold = 0.2

    class ServiceQuotaHelper(object):
        def set_quota(self, values):
            self.client.quotas.update(self.project_id, **values)

    class ServiceQuotaCinderHelper(ServiceQuotaHelper):
        def __init__(self, region_name, project_id):
            self.client = openstack_clients.get_cinderclient(region=region_name)
            self.project_id = project_id

        def get_quota(self):
            return self.client.quotas.get(self.project_id).to_dict()

        def get_usage(self):
            volumes = self.client.volumes.list(
                search_opts={"all_tenants": 1, "project_id": self.project_id}
            )
            snapshots = self.client.volume_snapshots.list(
                search_opts={"all_tenants": 1, "project_id": self.project_id}
            )

            # gigabytesUsed should be a total of volumes and snapshots
            gigabytes = sum([getattr(volume, "size", 0) for volume in volumes])
            gigabytes += sum([getattr(snap, "size", 0) for snap in snapshots])

            return {
                "gigabytes": gigabytes,
                "volumes": len(volumes),
                "snapshots": len(snapshots),
            }

    class ServiceQuotaNovaHelper(ServiceQuotaHelper):
        def __init__(self, region_name, project_id):
            self.client = openstack_clients.get_novaclient(region=region_name)
            self.project_id = project_id

        def get_quota(self):
            return self.client.quotas.get(self.project_id).to_dict()

        def get_usage(self):
            nova_usage = self.client.limits.get(tenant_id=self.project_id).to_dict()[
                "absolute"
            ]
            nova_usage_keys = [
                ("instances", "totalInstancesUsed"),
                ("floating_ips", "totalFloatingIpsUsed"),
                ("ram", "totalRAMUsed"),
                ("cores", "totalCoresUsed"),
                ("security_groups", "totalSecurityGroupsUsed"),
            ]

            nova_usage_dict = {}
            for key, usage_key in nova_usage_keys:
                nova_usage_dict[key] = nova_usage[usage_key]

            return nova_usage_dict

    class ServiceQuotaNeutronHelper(ServiceQuotaHelper):
        def __init__(self, region_name, project_id):
            self.client = openstack_clients.get_neutronclient(region=region_name)
            self.project_id = project_id

        def set_quota(self, values):
            body = {"quota": values}
            self.client.update_quota(self.project_id, body)

        def get_usage(self):
            networks = self.client.list_networks(tenant_id=self.project_id)["networks"]
            routers = self.client.list_routers(tenant_id=self.project_id)["routers"]
            floatingips = self.client.list_floatingips(tenant_id=self.project_id)[
                "floatingips"
            ]
            ports = self.client.list_ports(tenant_id=self.project_id)["ports"]
            subnets = self.client.list_subnets(tenant_id=self.project_id)["subnets"]
            security_groups = self.client.list_security_groups(
                tenant_id=self.project_id
            )["security_groups"]
            security_group_rules = self.client.list_security_group_rules(
                tenant_id=self.project_id
            )["security_group_rules"]

            return {
                "network": len(networks),
                "router": len(routers),
                "floatingip": len(floatingips),
                "port": len(ports),
                "subnet": len(subnets),
                "security_group": len(security_groups),
                "security_group_rule": len(security_group_rules),
            }

        def get_quota(self):
            return self.client.show_quota(self.project_id)["quota"]

    class ServiceQuotaOctaviaHelper(ServiceQuotaNeutronHelper):
        def __init__(self, region_name, project_id):
            self.client = openstack_clients.get_octaviaclient(region=region_name)
            self.project_id = project_id

        def get_quota(self):
            project_quota = self.client.quota_show(project_id=self.project_id)

            # NOTE(amelia): Instead of returning the default quota if ANY
            #               of the quotas are the default, the endpoint
            #               returns None
            default_quota = None
            for name, quota in project_quota.items():
                if quota is None:
                    if not default_quota:
                        default_quota = self.client.quota_defaults_show()["quota"]
                    project_quota[name] = default_quota[name]

            return project_quota

        def set_quota(self, values):
            self.client.quota_set(self.project_id, json={"quota": values})

        def get_usage(self):
            usage = {}
            usage["load_balancer"] = len(
                self.client.load_balancer_list(project_id=self.project_id)[
                    "loadbalancers"
                ]
            )
            usage["listener"] = len(
                self.client.listener_list(project_id=self.project_id)["listeners"]
            )

            pools = self.client.pool_list(project_id=self.project_id)["pools"]
            usage["pool"] = len(pools)

            members = []
            for pool in pools:
                members += pool["members"]

            usage["member"] = len(members)
            usage["health_monitor"] = len(
                self.client.health_monitor_list(project_id=self.project_id)[
                    "healthmonitors"
                ]
            )
            return usage

    class ServiceQuotaTroveHelper(ServiceQuotaHelper):
        def __init__(self, region_name, project_id):
            self.client = openstack_clients.get_troveclient(region=region_name)
            self.project_id = project_id

        def get_quota(self):
            project_quota = self.client.quota.show(self.project_id)

            quotas = {}
            for quota in project_quota:
                quotas[quota.resource] = quota.limit
            return quotas

        def set_quota(self, values):
            self.client.quota.update(self.project_id, values)

        def get_usage(self):
            project_quota = self.client.quota.show(self.project_id)

            usage = {}
            for quota in project_quota:
                usage[quota.resource] = quota.in_use

            return usage

    _quota_updaters = {
        "cinder": ServiceQuotaCinderHelper,
        "nova": ServiceQuotaNovaHelper,
        "neutron": ServiceQuotaNeutronHelper,
        "octavia": ServiceQuotaOctaviaHelper,
        "trove": ServiceQuotaTroveHelper,
    }

    def __init__(self, project_id, size_difference_threshold=None):
        # TODO(amelia): Try to find out which endpoints are available and get
        # the non enabled ones out of the list

        self.default_helpers = dict(self._quota_updaters)
        self.helpers = {}

        quota_services = dict(CONF.quota.services)

        all_regions = quota_services.pop("*", None)
        if all_regions:
            self.default_helpers = {}
            for service in all_regions:
                if service in self._quota_updaters:
                    self.default_helpers[service] = self._quota_updaters[service]

        for region, services in quota_services.items():
            self.helpers[region] = {}
            for service in services:
                if service in self._quota_updaters:
                    self.helpers[region][service] = self._quota_updaters[service]

        self.project_id = project_id
        self.size_diff_threshold = (
            size_difference_threshold or self.default_size_diff_threshold
        )

    def get_current_region_quota(self, region_id):
        current_quota = {}

        region_helpers = self.helpers.get(region_id, self.default_helpers)
        for name, service in region_helpers.items():
            helper = service(region_id, self.project_id)
            current_quota[name] = helper.get_quota()

        return current_quota

    def get_quota_differences(self, current_quota):
        """Gets the closest matching quota size for a given quota"""
        quota_differences = {}
        for size, setting in CONF.quota.sizes.items():
            match_percentages = []
            for service_name, values in setting.items():
                if service_name not in current_quota:
                    continue
                for name, value in values.items():
                    if name not in current_quota[service_name]:
                        continue
                    if value > 0:
                        current = current_quota[service_name][name]
                        dividend = float(min(current, value))
                        divisor = float(max(current, value))
                        match_percentages.append(dividend / divisor)
                    elif value < 0:
                        # NOTE(amelia): Sub-zero quota means unlimited
                        if current_quota[service_name][name] < 0:
                            match_percentages.append(1.0)
                        else:
                            match_percentages.append(0.0)
                    elif current_quota[service_name][name] == 0:
                        match_percentages.append(1.0)
                    else:
                        match_percentages.append(0.0)
            # Calculate the average of how much it matches the setting
            difference = abs(
                (sum(match_percentages) / float(len(match_percentages))) - 1
            )

            quota_differences[size] = difference

        return quota_differences

    def get_quota_size(self, current_quota, difference_threshold=None):
        """Gets the closest matching quota size for a given quota"""
        quota_differences = self.get_quota_differences(current_quota)

        diff_threshold = difference_threshold or self.size_diff_threshold

        quota_differences_pruned = {}
        for size, difference in quota_differences.items():
            if difference <= diff_threshold:
                quota_differences_pruned[size] = difference

        if len(quota_differences_pruned) > 0:
            return min(quota_differences_pruned, key=quota_differences_pruned.get)
        # If we don't get a match return custom which means the project will
        # need admin approval for any change
        return "custom"

    def get_quota_change_options(self, quota_size):
        """Get's the pre-approved quota change options for a given size"""
        quota_list = CONF.quota.sizes_ascending
        try:
            list_position = quota_list.index(quota_size)
        except ValueError:
            return []

        quota_change_list = quota_list[:list_position]

        if list_position + 1 < len(quota_list):
            quota_change_list.append(quota_list[list_position + 1])

        return quota_change_list

    def get_smaller_quota_options(self, quota_size):
        """Get the quota sizes smaller than the current size."""
        quota_list = CONF.quota.sizes_ascending
        try:
            list_position = quota_list.index(quota_size)
        except ValueError:
            return []

        return quota_list[:list_position]

    def get_region_quota_data(self, region_id, include_usage=True):
        current_quota = self.get_current_region_quota(region_id)
        current_quota_size = self.get_quota_size(current_quota)
        change_options = self.get_quota_change_options(current_quota_size)

        region_data = {
            "region": region_id,
            "current_quota": current_quota,
            "current_quota_size": current_quota_size,
            "quota_change_options": change_options,
        }

        if include_usage:
            region_data["current_usage"] = self.get_current_usage(region_id)

        return region_data

    def get_current_usage(self, region_id):
        current_usage = {}

        region_helpers = self.helpers.get(region_id, self.default_helpers)
        for name, service in region_helpers.items():
            helper = service(region_id, self.project_id)
            current_usage[name] = helper.get_usage()
        return current_usage

    def set_region_quota(self, region_id, quota_dict):
        notes = []
        for service_name, values in quota_dict.items():
            updater_class = self.helpers.get(region_id, self.default_helpers).get(
                service_name
            )
            if not updater_class:
                notes.append("No quota updater found for %s. Ignoring" % service_name)
                continue

            service_helper = updater_class(region_id, self.project_id)

            service_helper.set_quota(values)
        return notes
