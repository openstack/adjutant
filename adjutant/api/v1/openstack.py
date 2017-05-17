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
from django.utils import timezone

from rest_framework.response import Response

from adjutant.actions import user_store
from adjutant.api import models
from adjutant.api import utils
from adjutant.api.v1 import tasks
from adjutant.api.v1.utils import add_task_id_for_roles


class UserList(tasks.InviteUser):

    @utils.mod_or_admin
    def get(self, request):
        """Get a list of all users who have been added to a project"""
        class_conf = settings.TASK_SETTINGS.get(
            'edit_user', settings.DEFAULT_TASK_SETTINGS)
        role_blacklist = class_conf.get('role_blacklist', [])
        user_list = []
        id_manager = user_store.IdentityManager()
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)

        can_manage_roles = user_store.get_managable_roles(
            request.keystone_user['roles'])

        active_emails = set()
        for user in id_manager.list_users(project):
            skip = False
            roles = []
            for role in user.roles:
                if role.name in role_blacklist:
                    skip = True
                    continue
                roles.append(role.name)
            if skip:
                continue

            email = getattr(user, 'email', '')
            enabled = getattr(user, 'enabled')
            user_status = 'Active' if enabled else 'Account Disabled'
            active_emails.add(email)
            user_list.append({
                'id': user.id,
                'name': user.name,
                'email': email,
                'roles': roles,
                'cohort': 'Member',
                'status': user_status,
                'manageable': set(can_manage_roles).issuperset(roles),
            })

        # Get my active tasks for this project:
        project_tasks = models.Task.objects.filter(
            project_id=project_id,
            task_type="invite_user",
            completed=0,
            cancelled=0)

        registrations = []
        for task in project_tasks:
            status = "Invited"
            for token in task.tokens:
                if token.expired:
                    status = "Expired"

            for notification in task.notifications:
                if notification.error:
                    status = "Failed"

            task_data = {}
            for action in task.actions:
                task_data.update(action.action_data)

            registrations.append(
                {'uuid': task.uuid, 'task_data': task_data, 'status': status})

        for task in registrations:
            # NOTE(adriant): commenting out for now as it causes more confusion
            # than it helps. May uncomment once different duplication checking
            # measures are in place.
            # if task['task_data']['email'] not in active_emails:
            user = {'id': task['uuid'],
                    'name': task['task_data']['email'],
                    'email': task['task_data']['email'],
                    'roles': task['task_data']['roles'],
                    'cohort': 'Invited',
                    'status': task['status']}
            if not settings.USERNAME_IS_EMAIL:
                user['name'] = task['task_data']['username']

            user_list.append(user)

        return Response({'users': user_list})


class UserDetail(tasks.TaskView):
    task_type = 'edit_user'

    @utils.mod_or_admin
    def get(self, request, user_id):
        """
        Get user info based on the user id.

        Will only find users in your project.
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(user_id)

        no_user = {'errors': ['No user with this id.']}
        if not user:
            return Response(no_user, status=404)

        class_conf = settings.TASK_SETTINGS.get(
            self.task_type, settings.DEFAULT_TASK_SETTINGS)
        role_blacklist = class_conf.get('role_blacklist', [])
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)

        roles = [role.name for role in id_manager.get_roles(user, project)]
        roles_blacklisted = set(role_blacklist) & set(roles)

        if not roles or roles_blacklisted:
            return Response(no_user, status=404)
        return Response({'id': user.id,
                         "username": user.name,
                         "email": getattr(user, 'email', ''),
                         'roles': roles})

    @utils.mod_or_admin
    def delete(self, request, user_id):
        """
        Remove this user from the project.
        This may cancel a pending user invite, or simply revoke roles.
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(user_id)
        project_id = request.keystone_user['project_id']
        # NOTE(dale): For now, we only support cancelling pending invites.
        if user:
            return Response(
                {'errors': [
                    'Revoking keystone users not implemented. ' +
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

    default_actions = ['EditUserRolesAction', ]
    task_type = 'edit_roles'

    @utils.mod_or_admin
    def get(self, request, user_id):
        """ Get role info based on the user id. """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(user_id)
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)
        roles = []
        for role in id_manager.get_roles(user, project):
            roles.append(role.to_dict())
        return Response({"roles": roles})

    @utils.mod_or_admin
    def put(self, args, **kwargs):
        """ Add user roles to the current project. """
        kwargs['remove_role'] = False
        return self._edit_user(args, **kwargs)

    @utils.mod_or_admin
    def delete(self, args, **kwargs):
        """ Revoke user roles to the current project.

        This only supports Active users
        """
        kwargs['remove_role'] = True
        return self._edit_user(args, **kwargs)

    def _edit_user(self, request, user_id, remove_role=False, format=None):
        """ Helper function to add or remove roles from a user """
        request.data['remove'] = remove_role
        if 'project_id' not in request.data:
            request.data['project_id'] = request.keystone_user['project_id']
        request.data['user_id'] = user_id

        self.logger.info("(%s) - New EditUser %s request." % (
            timezone.now(), request.method))
        processed, status = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with registration." %
                             timezone.now())
            return Response(errors, status=status)

        response_dict = {'notes': processed.get('notes')}

        add_task_id_for_roles(request, processed, response_dict, ['admin'])

        return Response(response_dict, status=status)


class RoleList(tasks.TaskView):
    task_type = 'edit_roles'

    @utils.mod_or_admin
    def get(self, request):
        """Returns a list of roles that may be managed for this project"""

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


class UserResetPassword(tasks.ResetPassword):
    """
    The openstack forgot password endpoint.
    ---
    """

    def get(self, request):
        """
        The ResetPassword endpoint does not support GET.
        This returns a 404.
        """
        return Response(status=404)


class UserSetPassword(tasks.ResetPassword):
    """
    The openstack endpoint to force a password reset.
    ---
    """

    task_type = "force_password"

    def get(self, request):
        """
        The ForcePassword endpoint does not support GET.
        This returns a 404.
        """
        return Response(status=404)

    @utils.admin
    def post(self, request, format=None):
        return super(UserSetPassword, self).post(request)


class UserUpdateEmail(tasks.UpdateEmail):
    """
    The openstack endpoint for a user to update their own email.
    ---
    """

    def get(self, request):
        """
        The EmailUpdate endpoint does not support GET.
        This returns a 404.
        """
        return Response(status=404)


class SignUp(tasks.CreateProject):
    """
    The openstack endpoint for signups.
    """

    task_type = "signup"

    def get(self, request):
        """
        The SignUp endpoint does not support GET.
        This returns a 404.
        """
        return Response(status=404)

    def post(self, request, format=None):
        return super(SignUp, self).post(request)
