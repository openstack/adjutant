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

SECRET_KEY = '+er!!4olta#17a=n%uotcazg2ncpl==yjog%1*o-(cr%zys-)!'

ADDITIONAL_APPS = [
    'stacktask.api.v1',
    'stacktask.actions.tenant_setup'
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db.sqlite3'
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'reg_log.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'keystonemiddleware': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

EMAIL_SETTINGS = {
    "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend"
}

# setting to control if user name and email are allowed
# to have different values.
USERNAME_IS_EMAIL = True

# Keystone admin credentials:
KEYSTONE = {
    'username': 'admin',
    'password': 'openstack',
    'project_name': 'admin',
    'auth_url': "http://localhost:5000/v3"
}

DEFAULT_REGION = 'RegionOne'

TOKEN_SUBMISSION_URL = 'http://localhost:8080/token/'

TOKEN_EXPIRE_TIME = 24

DEFAULT_TASK_SETTINGS = {
    'emails': {
        'token': {
            'reply': 'no-reply@example.com',
            'template': 'token.txt',
            'subject': 'Your Token'
        },
        'initial': {
            'reply': 'no-reply@example.com',
            'template': 'initial.txt',
            'subject': 'Initial Confirmation'
        },
        'completed': {
            'reply': 'no-reply@example.com',
            'template': 'completed.txt',
            'subject': 'Task completed'
        }
    }
}

TASK_SETTINGS = {
    'invite_user': {
        'emails': {
            'initial': None,
            'token': {
                'template': 'invite_user_token.txt',
                'subject': 'invite_user'
            },
            'completed': {
                'template': 'invite_user_completed.txt',
                'subject': 'invite_user'
            }
        }
    },
    'create_project': {
        'actions': [
            'AddAdminToProject',
            'DefaultProjectResources'
        ]
    },
    'reset_password': {
        'handle_duplicates': 'cancel',
        'emails': {
            'token': {
                'template': 'password_reset_token.txt',
                'subject': 'Password Reset for OpenStack'
            },
            'completed': {
                'template': 'password_reset_completed.txt',
                'subject': 'Password Reset for OpenStack'
            }
        }
    },
    'force_password': {
        'handle_duplicates': 'cancel',
        'emails': {
            'token': {
                'template': 'initial_password_token.txt',
                'subject': 'Setup Your OpenStack Password'
            },
            'completed': {
                'template': 'initial_password_completed.txt',
                'subject': 'Setup Your OpenStack Password'
            }
        }
    }
}

ACTION_SETTINGS = {
    'NewUser': {
        'allowed_roles': ['project_mod', 'project_admin', "_member_"]
    },
    'ResetUser': {
        'blacklisted_roles': ['admin']
    },
    'DefaultProjectResources': {
        'RegionOne': {
            'DNS_NAMESERVERS': ['193.168.1.2', '193.168.1.3'],
            'SUBNET_CIDR': '192.168.1.0/24',
            'network_name': 'somenetwork',
            'public_network': '3cb50f61-5bce-4c03-96e6-8e262e12bb35',
            'router_name': 'somerouter',
            'subnet_name': 'somesubnet'
        }
    }
}

ROLES_MAPPING = {
    'admin': [
        'project_admin', 'project_mod', '_member_', 'heat_stack_owner'
    ],
    'project_admin': [
        'project_mod', '_member_', 'heat_stack_owner'
    ],
    'project_mod': [
        '_member_', 'heat_stack_owner'
    ],
}

SHOW_ACTION_ENDPOINTS = True

conf_dict = {
    "SECRET_KEY": SECRET_KEY,
    "ADDITIONAL_APPS": ADDITIONAL_APPS,
    "DATABASES": DATABASES,
    "LOGGING": LOGGING,
    "EMAIL_SETTINGS": EMAIL_SETTINGS,
    "USERNAME_IS_EMAIL": USERNAME_IS_EMAIL,
    "KEYSTONE": KEYSTONE,
    "DEFAULT_REGION": DEFAULT_REGION,
    "DEFAULT_TASK_SETTINGS": DEFAULT_TASK_SETTINGS,
    "TASK_SETTINGS": TASK_SETTINGS,
    "ACTION_SETTINGS": ACTION_SETTINGS,
    "TOKEN_SUBMISSION_URL": TOKEN_SUBMISSION_URL,
    "TOKEN_EXPIRE_TIME": TOKEN_EXPIRE_TIME,
    "ROLES_MAPPING": ROLES_MAPPING,
    "SHOW_ACTION_ENDPOINTS": SHOW_ACTION_ENDPOINTS
}
