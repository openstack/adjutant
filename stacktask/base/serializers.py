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


class BaseUserSerializer(serializers.Serializer):

    def __init__(self, *args, **kwargs):
        super(BaseUserSerializer, self).__init__(*args, **kwargs)

        if settings.USERNAME_IS_EMAIL:
            self.fields.pop('username')


class NewUserSerializer(BaseUserSerializer):
    username = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    project_id = serializers.CharField(max_length=200)

    # TODO(Adriant): These need to come from a config file I think:
    role_options = ['project_mod', 'project_owner', "Member"]
    roles = serializers.MultipleChoiceField(choices=role_options)


class NewProjectSerializer(BaseUserSerializer):
    project_name = serializers.CharField(max_length=200)
    username = serializers.CharField(max_length=200)
    email = serializers.EmailField()


class ResetUserSerializer(BaseUserSerializer):
    username = serializers.CharField(max_length=200)
    email = serializers.EmailField()


class EditUserSerializer(NewUserSerializer):
    remove = serializers.BooleanField(default=False)
