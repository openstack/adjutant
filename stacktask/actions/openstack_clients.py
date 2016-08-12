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


from django.conf import settings

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient import client as ks_client

from neutronclient.v2_0 import client as neutron_client


def get_keystoneclient():

    auth = v3.Password(
        username=settings.KEYSTONE['username'],
        password=settings.KEYSTONE['password'],
        project_name=settings.KEYSTONE['project_name'],
        auth_url=settings.KEYSTONE['auth_url'],
        user_domain_id=settings.KEYSTONE.get('domain_id', "default"),
        project_domain_id=settings.KEYSTONE.get('domain_id', "default"),
    )
    sess = session.Session(auth=auth)
    auth = ks_client.Client(session=sess)
    return auth


def get_neutronclient(region):
    auth = v3.Password(
        username=settings.KEYSTONE['username'],
        password=settings.KEYSTONE['password'],
        project_name=settings.KEYSTONE['project_name'],
        auth_url=settings.KEYSTONE['auth_url'],
        user_domain_id=settings.KEYSTONE.get('domain_id', "default"),
        project_domain_id=settings.KEYSTONE.get('domain_id', "default"),
    )
    sess = session.Session(auth=auth)
    neutron = neutron_client.Client(session=sess, region_name=region)
    return neutron
