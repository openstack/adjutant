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


from adjutant.actions.openstack_clients import (
    get_novaclient, get_cinderclient, get_neutronclient)

from django.conf import settings


class QuotaManager(object):
    """
    A manager to allow easier updating and access to quota information
    across all services.
    """

    default_size_diff_threshold = .2

    def __init__(self, project_id, size_difference_threshold=None):
        self.project_id = project_id
        self.size_diff_threshold = (size_difference_threshold or
                                    self.default_size_diff_threshold)

    def get_current_region_quota(self, region_id):
        ci_quota = get_cinderclient(region_id) \
            .quotas.get(self.project_id).to_dict()
        neutron_quota = get_neutronclient(region_id) \
            .show_quota(self.project_id)['quota']
        nova_quota = get_novaclient(region_id) \
            .quotas.get(self.project_id).to_dict()

        return {'cinder': ci_quota,
                'nova': nova_quota,
                'neutron': neutron_quota}

    def get_quota_size(self, current_quota, difference_threshold=None):
        """ Gets the closest matching quota size for a given quota """
        quota_differences = {}
        for size, setting in settings.PROJECT_QUOTA_SIZES.items():
            match_percentages = []
            for service_name, values in setting.items():
                for name, value in values.items():
                    if value != 0:
                        match_percentages.append(
                            float(current_quota[service_name][name]) / value)
            # Calculate the average of how much it matches the setting
            difference = abs(
                (sum(match_percentages) / float(len(match_percentages))) - 1)
            # TODO(amelia): Nicer form of this due to the new way of doing
            #               per action settings
            if (difference <= self.size_diff_threshold):
                quota_differences[size] = difference

        if len(quota_differences) > 0:
            return min(quota_differences, key=quota_differences.get)
        # If we don't get a match return custom which means the project will
        # need admin approval for any change
        return 'custom'

    def get_quota_change_options(self, quota_size):
        """ Get's the pre-approved quota change options for a given size """
        quota_list = settings.QUOTA_SIZES_ASC
        try:
            list_position = quota_list.index(quota_size)
        except ValueError:
            return []

        quota_change_list = []
        if list_position - 1 >= 0:
            quota_change_list.append(quota_list[list_position - 1])
        if list_position + 1 < len(quota_list):
            quota_change_list.append(quota_list[list_position + 1])

        return quota_change_list

    def get_region_quota_data(self, region_id):
        current_quota = self.get_current_region_quota(region_id)
        current_quota_size = self.get_quota_size(current_quota)
        change_options = self.get_quota_change_options(current_quota_size)
        current_usage = self.get_current_usage(region_id)
        return {'region': region_id,
                "current_quota": current_quota,
                "current_quota_size": current_quota_size,
                "quota_change_options": change_options,
                "current_usage": current_usage
                }

    def get_current_usage(self, region_id):
        cinder_usage = self.get_cinder_usage(region_id)
        nova_usage = self.get_nova_usage(region_id)
        neutron_usage = self.get_neutron_usage(region_id)
        return {'cinder': cinder_usage,
                'nova': nova_usage,
                'neutron': neutron_usage}

    def get_cinder_usage(self, region_id):
        client = get_cinderclient(region_id)

        volumes = client.volumes.list(
            search_opts={'all_tenants': 1, 'project_id': self.project_id})
        snapshots = client.volume_snapshots.list(
            search_opts={'all_tenants': 1, 'project_id': self.project_id})

        # gigabytesUsed should be a total of volumes and snapshots
        gigabytes = sum([getattr(volume, 'size', 0) for volume
                        in volumes])
        gigabytes += sum([getattr(snap, 'size', 0) for snap
                         in snapshots])

        return {'gigabytes': gigabytes,
                'volumes': len(volumes),
                'snapshots': len(snapshots)
                }

    def get_neutron_usage(self, region_id):
        client = get_neutronclient(region_id)

        networks = client.list_networks(
            tenant_id=self.project_id)['networks']
        routers = client.list_routers(
            tenant_id=self.project_id)['routers']
        floatingips = client.list_floatingips(
            tenant_id=self.project_id)['floatingips']
        ports = client.list_ports(
            tenant_id=self.project_id)['ports']
        subnets = client.list_subnets(
            tenant_id=self.project_id)['subnets']
        security_groups = client.list_security_groups(
            tenant_id=self.project_id)['security_groups']
        security_group_rules = client.list_security_group_rules(
            tenant_id=self.project_id)['security_group_rules']

        return {'network': len(networks),
                'router': len(routers),
                'floatingip': len(floatingips),
                'port': len(ports),
                'subnet': len(subnets),
                'secuirty_group': len(security_groups),
                'security_group_rule': len(security_group_rules)
                }

    def get_nova_usage(self, region_id):
        client = get_novaclient(region_id)
        nova_usage = client.limits.get(
            tenant_id=self.project_id).to_dict()['absolute']
        nova_usage_keys = [
            ('instances', 'totalInstancesUsed'),
            ('floating_ips', 'totalFloatingIpsUsed'),
            ('ram', 'totalRAMUsed'),
            ('cores', 'totalCoresUsed'),
            ('secuirty_groups', 'totalSecurityGroupsUsed')
        ]

        nova_usage_dict = {}
        for key, usage_key in nova_usage_keys:
            nova_usage_dict[key] = nova_usage[usage_key]

        return nova_usage_dict
