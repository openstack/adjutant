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

from rest_framework import serializers
from django.conf import settings


class NewUserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    project_id = serializers.CharField(max_length=200)

    role_options = (('project_mod', 'Project Owner (can add new users)'),
                    ('Member', "Project Member (can't add new users)"))
    role = serializers.ChoiceField(choices=role_options)

    def __init__(self, *args, **kwargs):
        super(NewUserSerializer, self).__init__(*args, **kwargs)

        if settings.USERNAME_IS_EMAIL:
            self.fields.pop('username')


class NewProjectSerializer(serializers.Serializer):
    project_name = serializers.CharField(max_length=200)
    username = serializers.CharField(max_length=200)
    email = serializers.EmailField()

    def __init__(self, *args, **kwargs):
        super(NewProjectSerializer, self).__init__(*args, **kwargs)

        if settings.USERNAME_IS_EMAIL:
            self.fields.pop('username')


class ResetUserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=200)
    email = serializers.EmailField()

    def __init__(self, *args, **kwargs):
        super(ResetUserSerializer, self).__init__(*args, **kwargs)

        if settings.USERNAME_IS_EMAIL:
            self.fields.pop('username')
