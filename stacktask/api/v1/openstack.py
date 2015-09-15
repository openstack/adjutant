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

from django.utils import timezone
from django.conf import settings
from rest_framework.response import Response

from stacktask.api.v1 import tasks
from stacktask.api import utils
from stacktask.base.user_store import IdentityManager


class UserList(tasks.InviteUser):

    @utils.mod_or_owner
    def get(self, request):
        """Get a list of all users who have been added to a tenant"""
        class_conf = settings.ACTIONVIEW_SETTINGS.get(self.__class__.__name__,
                                                      {})
        filters = class_conf.get('filters', [])
        user_list = []
        id_manager = IdentityManager()
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)

        for user in project.list_users():
            skip = False
            self.logger.info(user)
            roles = []
            for role in id_manager.get_roles(user, project):
                if role.name in filters:
                    skip = True
                    continue
                roles.append(role.name)
            if skip:
                continue
            email = ''
            if 'email' in user.to_dict():
                email = user.email
            user_list.append({'id': user.id,
                              'username': user.username,
                              'email': email,
                              'roles': roles})

        return Response({'users': user_list})


class UserDetail(tasks.TaskView):

    @utils.mod_or_owner
    def get(self, request, user_id):
        """
        Get user info based on the user id.
        """
        id_manager = IdentityManager()
        user = id_manager.get_user(user_id)
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)
        roles = []
        for role in id_manager.get_roles(user, project):
            roles.append(role.name)
        return Response({'id': user.id,
                         "username": user.username,
                         "email": user.username})


class UserRoles(tasks.TaskView):

    default_action = 'EditUser'

    @utils.mod_or_owner
    def get(self, request, user_id):
        """
        Get user info based on the user id.
        """
        id_manager = IdentityManager()
        user = id_manager.get_user(user_id)
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)
        roles = []
        for role in id_manager.get_roles(user, project):
            roles.append(role.name)
        return Response({"roles": roles})

    @utils.mod_or_owner
    def put(self, request, user_id, format=None):
        """
        Add user roles to the current tenant.
        """

        request.data['remove'] = False

        self.logger.info("(%s) - New EditUser request." % timezone.now())
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with registration." %
                             timezone.now())
            return Response(errors, status=400)

        registration = processed['registration']
        self.logger.info("(%s) - AutoApproving EditUser request."
                         % timezone.now())
        return self.approve(registration)

    @utils.mod_or_owner
    def delete(self, request, user_id, format=None):
        """
        Revoke user roles to the current tenant.
        """

        request.data['remove'] = True

        self.logger.info("(%s) - New EditUser request." % timezone.now())
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with registration." %
                             timezone.now())
            return Response(errors, status=400)

        registration = processed['registration']
        self.logger.info("(%s) - AutoApproving EditUser request."
                         % timezone.now())
        return self.approve(registration)


class RoleList(tasks.TaskView):

    @utils.mod_or_owner
    def get(self, request):
        """Returns a list of roles that may be managed for this tenant"""

        # get roles for this user on the project
        user_roles = request.keystone_user['roles']
        # hardcoded mapping between roles and managable roles
        # Todo: relocate to settings file.
        manage_mapping = {
            'admin': [
                'project_owner', 'project_mod', 'Member', 'heat_stack_user'
            ],
            'project_owner': [
                'project_mod', 'Member', 'heat_stack_user'
            ],
            'project_mod': [
                'Member', 'heat_stack_user'
            ],
        }
        # merge mapping lists to form a flat permitted roles list
        managable_role_names = [mrole for role in user_roles
                                if role.name in manage_mapping
                                for mrole in manage_mapping[role.name]]
        # a set has unique items
        managable_role_names = set(managable_role_names)

        id_manager = IdentityManager()

        # look up role names and form output dict of valid roles
        managable_roles = []
        for role_name in managable_role_names:
            role = id_manager.find_role(role_name)
            if role:
                managable_roles.append(role.to_dict())

        managable_roles = utils.get
        return Response({'roles': managable_roles})
