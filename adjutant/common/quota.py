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


from adjutant.common.openstack_clients import (
    get_novaclient, get_cinderclient, get_neutronclient)

from django.conf import settings


class QuotaManager(object):
    """
    A manager to allow easier updating and access to quota information
    across all services.
    """

    default_size_diff_threshold = .2

    class ServiceQuotaHelper(object):
        def set_quota(self, values):
            self.client.quotas.update(self.project_id, **values)

    class ServiceQuotaCinderHelper(ServiceQuotaHelper):
        def __init__(self, region_name, project_id):
            self.client = get_cinderclient(
                region=region_name)
            self.project_id = project_id

        def get_quota(self):
            return self.client.quotas.get(self.project_id).to_dict()

        def get_usage(self):
            volumes = self.client.volumes.list(
                search_opts={'all_tenants': 1, 'project_id': self.project_id})
            snapshots = self.client.volume_snapshots.list(
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

    class ServiceQuotaNovaHelper(ServiceQuotaHelper):
        def __init__(self, region_name, project_id):
            self.client = get_novaclient(
                region=region_name)
            self.project_id = project_id

        def get_quota(self):
            return self.client.quotas.get(self.project_id).to_dict()

        def get_usage(self):
            nova_usage = self.client.limits.get(
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

    class ServiceQuotaNeutronHelper(ServiceQuotaHelper):
        def __init__(self, region_name, project_id):
            self.client = get_neutronclient(
                region=region_name)
            self.project_id = project_id

        def set_quota(self, values):
            body = {
                'quota': values
            }
            self.client.update_quota(self.project_id, body)

        def get_usage(self):
            networks = self.client.list_networks(
                tenant_id=self.project_id)['networks']
            routers = self.client.list_routers(
                tenant_id=self.project_id)['routers']
            floatingips = self.client.list_floatingips(
                tenant_id=self.project_id)['floatingips']
            ports = self.client.list_ports(
                tenant_id=self.project_id)['ports']
            subnets = self.client.list_subnets(
                tenant_id=self.project_id)['subnets']
            security_groups = self.client.list_security_groups(
                tenant_id=self.project_id)['security_groups']
            security_group_rules = self.client.list_security_group_rules(
                tenant_id=self.project_id)['security_group_rules']

            return {'network': len(networks),
                    'router': len(routers),
                    'floatingip': len(floatingips),
                    'port': len(ports),
                    'subnet': len(subnets),
                    'secuirty_group': len(security_groups),
                    'security_group_rule': len(security_group_rules)
                    }

        def get_quota(self):
            return self.client.show_quota(self.project_id)['quota']

    _quota_updaters = {
        'cinder': ServiceQuotaCinderHelper,
        'nova': ServiceQuotaNovaHelper,
        'neutron': ServiceQuotaNeutronHelper
    }

    def __init__(self, project_id, size_difference_threshold=None):
        # TODO(amelia): Try to find out which endpoints are available and get
        # the non enabled ones out of the list

        # Check configured removal of quota updaters
        self.helpers = dict(self._quota_updaters)

        # Configurable services
        if settings.QUOTA_SERVICES:
            self.helpers = {}
            for name in settings.QUOTA_SERVICES:
                if name in self._quota_updaters:
                    self.helpers[name] = self._quota_updaters[name]

        self.project_id = project_id
        self.size_diff_threshold = (size_difference_threshold or
                                    self.default_size_diff_threshold)

    def get_current_region_quota(self, region_id):
        current_quota = {}
        for name, service in self.helpers.items():
            helper = service(region_id, self.project_id)
            current_quota[name] = helper.get_quota()

        return current_quota

    def get_quota_size(self, current_quota, difference_threshold=None):
        """ Gets the closest matching quota size for a given quota """
        quota_differences = {}
        for size, setting in settings.PROJECT_QUOTA_SIZES.items():
            match_percentages = []
            for service_name, values in setting.items():
                for name, value in values.items():
                    if value != 0:
                        try:
                            current = current_quota[service_name][name]
                            match_percentages.append(float(current) / value)
                        except KeyError:
                            pass
                    elif current_quota[service_name][name] == 0:
                        match_percentages.append(1.0)
                    else:
                        match_percentages.append(0.0)
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
        current_usage = {}

        for name, service in self.helpers.items():
            try:
                helper = service(region_id, self.project_id)
                current_usage[name] = helper.get_usage()
            except Exception:
                pass
        return current_usage

    def set_region_quota(self, region_id, quota_dict):
        notes = []
        for service_name, values in quota_dict.items():
            updater_class = self.helpers.get(service_name)
            if not updater_class:
                notes.append("No quota updater found for %s. Ignoring" %
                             service_name)
                continue

            try:
                service_helper = updater_class(region_id, self.project_id)
            except Exception:
                # NOTE(amelia): We will assume if there are issues connecting
                #               to a service that it will be due to the
                #               service not existing in this region.
                notes.append("Couldn't access %s client, region %s" %
                             (service_name, region_id))
                continue

            service_helper.set_quota(values)
        return notes
