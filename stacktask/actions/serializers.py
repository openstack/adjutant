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

from rest_framework import serializers
from django.conf import settings


role_options = settings.ACTION_SETTINGS.get("NewUser", {}).get(
    "allowed_roles", [])


class BaseUserNameSerializer(serializers.Serializer):
    """
    A serializer where the user is identified by username/email.
    """
    username = serializers.CharField(max_length=200)
    email = serializers.EmailField()

    def __init__(self, *args, **kwargs):
        super(BaseUserNameSerializer, self).__init__(*args, **kwargs)

        if settings.USERNAME_IS_EMAIL:
            self.fields.pop('username')


class BaseUserIdSerializer(serializers.Serializer):
    user_id = serializers.CharField(max_length=200)


class NewUserSerializer(BaseUserNameSerializer):
    roles = serializers.MultipleChoiceField(choices=role_options)
    project_id = serializers.CharField(max_length=200)
    pass


class NewProjectSerializer(BaseUserNameSerializer):
    project_name = serializers.CharField(max_length=200)


class ResetUserSerializer(BaseUserNameSerializer):
    pass


class EditUserSerializer(BaseUserIdSerializer):
    roles = serializers.MultipleChoiceField(choices=role_options)
    remove = serializers.BooleanField(default=False)
    project_id = serializers.CharField(max_length=200)
