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

# clients = {}


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
        username="admin",
        password="openstack",
        tenant_name="demo",
        auth_url="http://localhost:5000/v2.0",
        insecure=True
    )
    return auth
