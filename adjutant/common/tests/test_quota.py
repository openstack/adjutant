# Copyright (C) 2026 Catalyst Cloud Limited
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

from unittest import mock
from adjutant.common.tests.utils import AdjutantTestCase
from adjutant.common.quota import QuotaManager


class TestAodhQuotaHelper(AdjutantTestCase):

    def setUp(self):
        super(TestAodhQuotaHelper, self).setUp()
        self.project_id = "test-project-uuid"
        self.region = "RegionOne"

    @mock.patch("adjutant.common.openstack_clients.get_aodhclient")
    def test_get_quota_flattens_nested_dict(self, mock_get_client):
        """Test that Aodh's nested API response is flattened correctly."""

        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.quota.list.return_value = {
            "project_id": self.project_id,
            "quotas": [{"resource": "alarms", "limit": 400}],
        }

        helper = QuotaManager.ServiceQuotaAodhHelper(self.region, self.project_id)
        result = helper.get_quota()

        self.assertEqual(result, {"alarms": 400})
        mock_client.quota.list.assert_called_once_with(project=self.project_id)

    @mock.patch("adjutant.common.openstack_clients.get_aodhclient")
    def test_set_quota_transforms_to_list(self, mock_get_client):
        """Test that Adjutant's dict is transformed into Aodh's required list."""

        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        helper = QuotaManager.ServiceQuotaAodhHelper(self.region, self.project_id)
        helper.set_quota({"alarms": 150})

        expected_list = [{"resource": "alarms", "limit": 150}]
        mock_client.quota.create.assert_called_once_with(self.project_id, expected_list)

    @mock.patch("adjutant.common.openstack_clients.get_aodhclient")
    def test_get_usage_counts_alarms(self, mock_get_client):
        """Test that usage calculates the length of the returned alarms."""

        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.alarm.list.return_value = ["alarm1", "alarm2", "alarm3"]

        helper = QuotaManager.ServiceQuotaAodhHelper(self.region, self.project_id)
        result = helper.get_usage()

        self.assertEqual(result, {"alarms": 3})
