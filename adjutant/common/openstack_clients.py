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


from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient import client as ks_client

from cinderclient import client as cinderclient
from neutronclient.v2_0 import client as neutronclient
from novaclient import client as novaclient
from octaviaclient.api.v2 import octavia
from troveclient.v1 import client as troveclient

from adjutant.config import CONF

# Defined for use locally
DEFAULT_COMPUTE_VERSION = "2"
DEFAULT_IDENTITY_VERSION = "3"
DEFAULT_IMAGE_VERSION = "2"
DEFAULT_METERING_VERSION = "2"
DEFAULT_OBJECT_STORAGE_VERSION = "1"
DEFAULT_ORCHESTRATION_VERSION = "1"
DEFAULT_VOLUME_VERSION = "3"

# Auth session shared by default with all clients
client_auth_session = None


def get_auth_session():
    """Returns a global auth session to be shared by all clients"""
    global client_auth_session
    if not client_auth_session:

        auth = v3.Password(
            username=CONF.identity.auth.username,
            password=CONF.identity.auth.password,
            project_name=CONF.identity.auth.project_name,
            auth_url=CONF.identity.auth.auth_url,
            user_domain_id=CONF.identity.auth.user_domain_id,
            project_domain_id=CONF.identity.auth.project_domain_id,
        )
        client_auth_session = session.Session(auth=auth)

    return client_auth_session


def get_keystoneclient(version=DEFAULT_IDENTITY_VERSION):
    return ks_client.Client(version, session=get_auth_session())


def get_neutronclient(region):
    # always returns neutron client v2
    return neutronclient.Client(session=get_auth_session(), region_name=region)


def get_novaclient(region, version=DEFAULT_COMPUTE_VERSION):
    return novaclient.Client(version, session=get_auth_session(), region_name=region)


def get_cinderclient(region, version=DEFAULT_VOLUME_VERSION):
    return cinderclient.Client(version, session=get_auth_session(), region_name=region)


def get_octaviaclient(region):
    ks = get_keystoneclient()

    service = ks.services.list(name="octavia")[0]
    endpoint = ks.endpoints.list(service=service, region=region, interface="public")[0]
    return octavia.OctaviaAPI(session=get_auth_session(), endpoint=endpoint.url)


def get_troveclient(region):
    return troveclient.Client(session=get_auth_session(), region_name=region)
