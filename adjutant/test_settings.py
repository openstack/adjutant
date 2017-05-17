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

SECRET_KEY = '+er!4olta#17a=n%uotcazg2ncpl==yjog%1*o-(cr%zys-)!'

ADDITIONAL_APPS = [
    'adjutant.api.v1',
    'adjutant.actions.v1',
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
        'adjutant': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'keystonemiddleware': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
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
    'auth_url': "http://localhost:5000/v3",
}

TOKEN_SUBMISSION_URL = 'http://localhost:8080/token/'

TOKEN_EXPIRE_TIME = 24

ACTIVE_TASKVIEWS = [
    'UserRoles',
    'UserDetail',
    'UserResetPassword',
    'UserSetPassword',
    'UserList',
    'RoleList',
    'CreateProject',
    'InviteUser',
    'ResetPassword',
    'EditUser',
    'UpdateEmail'
]

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

DEFAULT_ACTION_SETTINGS = {
    'NewProjectAction': {
        'default_roles': {
            "project_admin", "project_mod", "_member_", "heat_stack_owner"
        },
    },
    'NewProjectWithUserAction': {
        'default_roles': {
            "project_admin", "project_mod", "_member_", "heat_stack_owner"
        },
    },
    'NewUserAction': {
        'allowed_roles': ['project_mod', 'project_admin', "_member_"]
    },
    'NewDefaultNetworkAction': {
        'RegionOne': {
            'DNS_NAMESERVERS': ['193.168.1.2', '193.168.1.3'],
            'SUBNET_CIDR': '192.168.1.0/24',
            'network_name': 'somenetwork',
            'public_network': '3cb50f61-5bce-4c03-96e6-8e262e12bb35',
            'router_name': 'somerouter',
            'subnet_name': 'somesubnet'
        },
    },
    'NewProjectDefaultNetworkAction': {
        'RegionOne': {
            'DNS_NAMESERVERS': ['193.168.1.2', '193.168.1.3'],
            'SUBNET_CIDR': '192.168.1.0/24',
            'network_name': 'somenetwork',
            'public_network': '3cb50f61-5bce-4c03-96e6-8e262e12bb35',
            'router_name': 'somerouter',
            'subnet_name': 'somesubnet'
        },
    },
    'SetProjectQuotaAction': {
        'regions': {
            'RegionOne': {
                'quota_size': 'small'
            },
            'RegionTwo': {
                'quota_size': 'large'
            }
        },
    },
    'SendAdditionalEmailAction': {
        'initial': {
            'reply': 'no-reply@example.com',
            'from': 'bounce+%(task_uuid)s@example.com'
        },
        'token': {
            'reply': 'no-reply@example.com',
            'from': 'bounce+%(task_uuid)s@example.com'
        },
        'completed': {
            'reply': 'no-reply@example.com',
            'from': 'bounce+%(task_uuid)s@example.com'
        },
    },
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
        'emails': {
            'initial': {
                'template': 'signup_initial.txt',
                'subject': 'signup received'
            },
            'token': {
                'template': 'signup_token.txt',
                'subject': 'signup approved'
            },
            'completed': {
                'template': 'signup_completed.txt',
                'subject': 'signup completed'
            }
        },
        'additional_actions': [
            'AddDefaultUsersToProjectAction',
            'NewProjectDefaultNetworkAction'
        ],
        'default_region': 'RegionOne',
        'default_parent_id': None,
    },
    'reset_password': {
        'duplicate_policy': 'cancel',
        'emails': {
            'initial': None,
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
        'duplicate_policy': 'cancel',
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
    },
    'update_email': {
        'emails': {
            'initial': None,
        },
    },
}

ROLES_MAPPING = {
    'admin': [
        'project_admin', 'project_mod', '_member_', 'heat_stack_owner'
    ],
    'project_admin': [
        'project_mod', '_member_', 'heat_stack_owner', 'project_admin',
    ],
    'project_mod': [
        '_member_', 'heat_stack_owner', 'project_mod',
    ],
}

PROJECT_QUOTA_SIZES = {
    'small': {
        'nova': {
            'instances': 10,
            'cores': 20,
            'ram': 65536,
            'floating_ips': 10,
            'fixed_ips': 0,
            'metadata_items': 128,
            'injected_files': 5,
            'injected_file_content_bytes': 10240,
            'key_pairs': 50,
            'security_groups': 20,
            'security_group_rules': 100,
        },
        'cinder': {
            'gigabytes': 5000,
            'snapshots': 50,
            'volumes': 20,
        },
        'neutron': {
            'floatingip': 10,
            'network': 3,
            'port': 50,
            'router': 3,
            'security_group': 20,
            'security_group_rule': 100,
            'subnet': 3,
        },
    },
    'large': {
        'cinder': {
            'gigabytes': 73571,
            'snapshots': 73572,
            'volumes': 73573,
        },
    },
}

SHOW_ACTION_ENDPOINTS = True

conf_dict = {
    "DEBUG": True,
    "SECRET_KEY": SECRET_KEY,
    "ADDITIONAL_APPS": ADDITIONAL_APPS,
    "DATABASES": DATABASES,
    "LOGGING": LOGGING,
    "EMAIL_SETTINGS": EMAIL_SETTINGS,
    "USERNAME_IS_EMAIL": USERNAME_IS_EMAIL,
    "KEYSTONE": KEYSTONE,
    "ACTIVE_TASKVIEWS": ACTIVE_TASKVIEWS,
    "DEFAULT_TASK_SETTINGS": DEFAULT_TASK_SETTINGS,
    "TASK_SETTINGS": TASK_SETTINGS,
    "DEFAULT_ACTION_SETTINGS": DEFAULT_ACTION_SETTINGS,
    "TOKEN_SUBMISSION_URL": TOKEN_SUBMISSION_URL,
    "TOKEN_EXPIRE_TIME": TOKEN_EXPIRE_TIME,
    "ROLES_MAPPING": ROLES_MAPPING,
    "PROJECT_QUOTA_SIZES": PROJECT_QUOTA_SIZES,
    "SHOW_ACTION_ENDPOINTS": SHOW_ACTION_ENDPOINTS,
}
