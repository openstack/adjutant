# Copyright (C) 2014 Catalyst IT Ltd
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

from keystoneclient.v2_0 import client
from neutronclient.v2_0 import client as neutron_client

from django.conf import settings


def get_keystoneclient():
    # try:
    #     return clients['keystone']
    # except KeyError:
    #     auth = v3.Password(
    #             auth_url='http://10.0.2.15:5000/v3',
    #             user_id='admin',
    #             password='openstack',
    #             project_name='admin'
    #     )
    #     sess = session.Session(auth=auth)
    #     keystone = KeystoneClient.Client(session=sess)
    #     clients['keystone'] = keystone
    auth = client.Client(
        username=settings.KEYSTONE['username'],
        password=settings.KEYSTONE['password'],
        tenant_name=settings.KEYSTONE['project_name'],
        auth_url=settings.KEYSTONE['auth_url']
    )
    return auth


def get_neutronclient():
    neutron = neutron_client.Client(
        username=settings.KEYSTONE['username'],
        password=settings.KEYSTONE['password'],
        tenant_name=settings.KEYSTONE['project_name'],
        auth_url=settings.KEYSTONE['auth_url'])
    return neutron
