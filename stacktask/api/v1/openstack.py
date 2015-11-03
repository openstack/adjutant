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
from stacktask.api import models
from stacktask.actions import user_store


class UserList(tasks.InviteUser):

    @utils.mod_or_owner
    def get(self, request):
        """Get a list of all users who have been added to a tenant"""
        class_conf = settings.TASK_SETTINGS.get('edit_user', {})
        filters = class_conf.get('filters', [])
        user_list = []
        id_manager = user_store.IdentityManager()
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)

        active_emails = set()
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

            email = getattr(user, 'email', '')
            active_emails.add(email)
            user_list.append({'id': user.id,
                              'name': user.username,
                              'email': email,
                              'roles': roles,
                              'status': 'Active'
                              })

        # Get my active tasks for this project:
        project_tasks = models.Task.objects.filter(
            project_id=project_id,
            task_type="invite_user",
            completed=0,
            cancelled=0)

        # get the actions for the related tasks
        # NOTE(adriant): We should later check for the correct action type
        # if this task_type ends up having more than one.
        registrations = []
        for task in project_tasks:
            registrations.extend(task.actions)

        unconfirmed = set()
        for action in registrations:
            # NOTE(flwang): If there are duplicated registrations, we need to
            # make sure it's filtered.
            if (action.action_data['email'] not in unconfirmed and
                    action.action_data['email'] not in active_emails):
                unconfirmed.add(action.action_data['email'])
                user_list.append({'id': action.task.uuid,
                                  'name': action.action_data['email'],
                                  'email': action.action_data['email'],
                                  'roles': action.action_data['roles'],
                                  'status': 'Unconfirmed'})

        return Response({'users': user_list})


class UserDetail(tasks.TaskView):
    task_type = 'edit_user'

    @utils.mod_or_owner
    def get(self, request, user_id):
        """
        Get user info based on the user id.
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(user_id)
        if not user:
            return Response({'errors': ['No user with this id.']},
                            status=404)
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)
        roles = []
        for role in id_manager.get_roles(user, project):
            roles.append(role.name)
        return Response({'id': user.id,
                         "username": user.username,
                         "email": getattr(user, 'email', ''),
                         'roles': roles})

    @utils.mod_or_owner
    def delete(self, request, user_id):
        """
        Remove this user from the tenant.
        This may cancel a pending user invite, or simply revoke roles.
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(user_id)
        project_id = request.data['project_id'] or request.keystone_user['project_id']
        # NOTE(dale): For now, we only support cancelling pending invites.
        if user:
            return Response({'errors':
                            ['Revoking keystone users not implemented. ' +
                            'Try removing all roles instead.']},
                            status=501)
        project_tasks = models.Task.objects.filter(
            project_id=project_id,
            task_type="invite_user",
            completed=0,
            cancelled=0)
        for task in project_tasks:
            if task.uuid == user_id:
                task.add_action_note(self.__class__.__name__, 'Cancelled.')
                task.cancelled = True
                task.save()
                return Response('Cancelled pending invite task!', status=200)
        return Response('Not found.', status=404)


class UserRoles(tasks.TaskView):

    default_action = 'EditUserRoles'
    task_type = 'edit_roles'

    @utils.mod_or_owner
    def get(self, request, user_id):
        """
        Get user info based on the user id.
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(user_id)
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)
        roles = []
        for role in id_manager.get_roles(user, project):
            roles.append(role.to_dict())
        return Response({"roles": roles})

    @utils.mod_or_owner
    def put(self, request, user_id, format=None):
        """
        Add user roles to the current tenant.
        """
        request.data['remove'] = False
        if 'project_id' not in request.data:
            request.data['project_id'] = request.keystone_user['project_id']
        request.data['user_id'] = user_id

        self.logger.info("(%s) - New EditUserRoles request." % timezone.now())
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with registration." %
                             timezone.now())
            return Response(errors, status=400)

        task = processed['task']
        self.logger.info("(%s) - AutoApproving EditUserRoles request."
                         % timezone.now())
        return self.approve(task)

    @utils.mod_or_owner
    def delete(self, request, user_id, format=None):
        """
        Revoke user roles to the current tenant.
        This only supports Active users.
        """
        request.data['remove'] = True
        if 'project_id' not in request.data:
            request.data['project_id'] = request.keystone_user['project_id']
        request.data['user_id'] = user_id

        self.logger.info("(%s) - New EditUser request." % timezone.now())
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with registration." %
                             timezone.now())
            return Response(errors, status=400)

        task = processed['task']
        self.logger.info("(%s) - AutoApproving EditUser request."
                         % timezone.now())
        return self.approve(task)


class RoleList(tasks.TaskView):
    task_type = 'edit_roles'

    @utils.mod_or_owner
    def get(self, request):
        """Returns a list of roles that may be managed for this tenant"""

        # get roles for this user on the project
        user_roles = request.keystone_user['roles']
        managable_role_names = user_store.get_managable_roles(user_roles)

        id_manager = user_store.IdentityManager()

        # look up role names and form output dict of valid roles
        managable_roles = []
        for role_name in managable_role_names:
            role = id_manager.find_role(role_name)
            if role:
                managable_roles.append(role.to_dict())

        return Response({'roles': managable_roles})
