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

from rest_framework.response import Response

from confspirator import groups
from confspirator import fields

from adjutant.common import user_store
from adjutant.api import models
from adjutant.api import utils
from adjutant.api.v1 import tasks
from adjutant.api.v1.base import BaseDelegateAPI
from adjutant.common.quota import QuotaManager
from adjutant.config import CONF


class UserList(tasks.InviteUser):

    url = r"^openstack/users/?$"

    config_group = groups.DynamicNameConfigGroup(
        children=[
            fields.ListConfig(
                "blacklisted_roles",
                help_text="Users with any of these roles will be hidden from the user list.",
                default=[],
                sample_default=["admin"],
            ),
        ]
    )

    @utils.mod_or_admin
    def get(self, request):
        """Get a list of all users who have been added to a project"""
        class_conf = self.config
        blacklisted_roles = class_conf.blacklisted_roles

        user_list = []
        id_manager = user_store.IdentityManager()
        project_id = request.keystone_user["project_id"]
        project = id_manager.get_project(project_id)

        can_manage_roles = id_manager.get_manageable_roles(
            request.keystone_user["roles"]
        )

        active_emails = set()
        for user in id_manager.list_users(project):
            skip = False
            roles = []
            for role in user.roles:
                if role.name in blacklisted_roles:
                    skip = True
                    continue
                roles.append(role.name)
            if skip:
                continue
            inherited_roles = []
            for role in user.inherited_roles:
                if role.name in blacklisted_roles:
                    skip = True
                    continue
                inherited_roles.append(role.name)
            if skip:
                continue

            email = getattr(user, "email", "")
            enabled = user.enabled
            user_status = "Active" if enabled else "Account Disabled"
            active_emails.add(email)
            user_list.append(
                {
                    "id": user.id,
                    "name": user.name,
                    "email": email,
                    "roles": roles,
                    "inherited_roles": inherited_roles,
                    "cohort": "Member",
                    "status": user_status,
                    "manageable": set(can_manage_roles).issuperset(roles),
                }
            )

        for user in id_manager.list_inherited_users(project):
            skip = False
            roles = []
            for role in user.roles:
                if role.name in blacklisted_roles:
                    skip = True
                    continue
                roles.append(role.name)
            if skip:
                continue

            email = getattr(user, "email", "")
            enabled = user.enabled
            user_status = "Active" if enabled else "Account Disabled"
            user_list.append(
                {
                    "id": user.id,
                    "name": user.name,
                    "email": email,
                    "roles": roles,
                    "inherited_roles": [],
                    "cohort": "Inherited",
                    "status": user_status,
                    "manageable": False,
                }
            )

        # Get my active tasks for this project:
        project_tasks = models.Task.objects.filter(
            project_id=project_id,
            task_type="invite_user_to_project",
            completed=0,
            cancelled=0,
        )

        registrations = []
        for task in project_tasks:
            status = "Invited"
            for token in task.tokens:
                if token.expired:
                    status = "Expired"

            for notification in task.notifications:
                if notification.error:
                    status = "Failed"

            for action in task.actions:
                if not action.valid:
                    status = "Invalid"

            task_data = {}
            for action in task.actions:
                task_data.update(action.action_data)

            registrations.append(
                {"uuid": task.uuid, "task_data": task_data, "status": status}
            )

        for task in registrations:
            # NOTE(adriant): commenting out for now as it causes more confusion
            # than it helps. May uncomment once different duplication checking
            # measures are in place.
            # if task['task_data']['email'] not in active_emails:
            user = {
                "id": task["uuid"],
                "name": task["task_data"]["email"],
                "email": task["task_data"]["email"],
                "roles": task["task_data"]["roles"],
                "inherited_roles": task["task_data"]["inherited_roles"],
                "cohort": "Invited",
                "status": task["status"],
            }
            if not CONF.identity.username_is_email:
                user["name"] = task["task_data"]["username"]

            user_list.append(user)

        return Response({"users": user_list})


class UserDetail(BaseDelegateAPI):

    url = r"^openstack/users/(?P<user_id>\w+)/?$"

    config_group = groups.DynamicNameConfigGroup(
        children=[
            fields.ListConfig(
                "blacklisted_roles",
                help_text="User with these roles will return not found.",
                default=[],
                sample_default=["admin"],
            ),
        ]
    )

    @utils.mod_or_admin
    def get(self, request, user_id):
        """
        Get user info based on the user id.

        Will only find users in your project.
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(user_id)

        no_user = {"errors": ["No user with this id."]}
        if not user:
            return Response(no_user, status=404)

        class_conf = self.config
        blacklisted_roles = class_conf.blacklisted_roles

        project_id = request.keystone_user["project_id"]
        project = id_manager.get_project(project_id)

        roles = [role.name for role in id_manager.get_roles(user, project)]
        roles_blacklisted = set(blacklisted_roles) & set(roles)
        inherited_roles = [
            role.name for role in id_manager.get_roles(user, project, True)
        ]
        inherited_roles_blacklisted = set(blacklisted_roles) & set(inherited_roles)

        if not roles or roles_blacklisted or inherited_roles_blacklisted:
            return Response(no_user, status=404)
        return Response(
            {
                "id": user.id,
                "username": user.name,
                "email": getattr(user, "email", ""),
                "roles": roles,
                "inherited_roles": inherited_roles,
            }
        )

    @utils.mod_or_admin
    def delete(self, request, user_id):
        """
        Remove this user from the project.
        This may cancel a pending user invite, or simply revoke roles.
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(user_id)
        project_id = request.keystone_user["project_id"]
        # NOTE(dale): For now, we only support cancelling pending invites.
        if user:
            return Response(
                {
                    "errors": [
                        "Revoking keystone users not implemented. "
                        "Try removing all roles instead."
                    ]
                },
                status=501,
            )
        project_tasks = models.Task.objects.filter(
            project_id=project_id,
            task_type="invite_user_to_project",
            completed=0,
            cancelled=0,
        )
        for task in project_tasks:
            if task.uuid == user_id:
                self.task_manager.cancel(task)
                return Response("Cancelled pending invite task!", status=200)
        return Response("Not found.", status=404)


class UserRoles(BaseDelegateAPI):

    url = r"^openstack/users/(?P<user_id>\w+)/roles/?$"

    config_group = groups.DynamicNameConfigGroup(
        children=[
            fields.ListConfig(
                "blacklisted_roles",
                help_text="User with these roles will return not found.",
                default=[],
                sample_default=["admin"],
            ),
        ]
    )

    task_type = "edit_user_roles"

    @utils.mod_or_admin
    def get(self, request, user_id):
        """Get role info based on the user id."""
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(user_id)

        no_user = {"errors": ["No user with this id."]}
        if not user:
            return Response(no_user, status=404)

        project_id = request.keystone_user["project_id"]
        project = id_manager.get_project(project_id)

        class_conf = self.config
        blacklisted_roles = class_conf.blacklisted_roles

        roles = [role.name for role in id_manager.get_roles(user, project)]
        roles_blacklisted = set(blacklisted_roles) & set(roles)
        inherited_roles = [
            role.name for role in id_manager.get_roles(user, project, True)
        ]
        inherited_roles_blacklisted = set(blacklisted_roles) & set(inherited_roles)

        if not roles or roles_blacklisted or inherited_roles_blacklisted:
            return Response(no_user, status=404)
        return Response({"roles": roles, "inherited_roles": inherited_roles})

    @utils.mod_or_admin
    def put(self, args, **kwargs):
        """Add user roles to the current project."""
        kwargs["remove_role"] = False
        return self._edit_user(args, **kwargs)

    @utils.mod_or_admin
    def delete(self, args, **kwargs):
        """Revoke user roles to the current project.

        This only supports Active users
        """
        kwargs["remove_role"] = True
        return self._edit_user(args, **kwargs)

    def _edit_user(self, request, user_id, remove_role=False, format=None):
        """Helper function to add or remove roles from a user"""
        request.data["remove"] = remove_role
        if "project_id" not in request.data:
            request.data["project_id"] = request.keystone_user["project_id"]
        request.data["user_id"] = user_id

        self.logger.info(
            "(%s) - New EditUser %s request." % (timezone.now(), request.method)
        )

        self.task_manager.create_from_request(self.task_type, request)

        return Response({"notes": ["task created"]}, status=202)


class RoleList(BaseDelegateAPI):

    url = r"^openstack/roles/?$"

    @utils.mod_or_admin
    def get(self, request):
        """Returns a list of roles that may be managed for this project"""

        # get roles for this user on the project
        user_roles = request.keystone_user["roles"]

        id_manager = user_store.IdentityManager()
        manageable_role_names = id_manager.get_manageable_roles(user_roles)

        # look up role names and form output dict of valid roles
        manageable_roles = []
        for role_name in manageable_role_names:
            role = id_manager.find_role(role_name)
            if role:
                manageable_roles.append(role.to_dict())

        return Response({"roles": manageable_roles})


class UserResetPassword(tasks.ResetPassword):
    """
    The openstack forgot password endpoint.
    ---
    """

    url = r"^openstack/users/password-reset/?$"

    pass


class UserUpdateEmail(tasks.UpdateEmail):
    """
    The openstack endpoint for a user to update their own email.
    ---
    """

    url = r"^openstack/users/email-update/?$"

    pass


class SignUp(tasks.CreateProjectAndUser):
    """
    The openstack endpoint for signups.
    """

    url = r"^openstack/sign-up/?$"

    pass


class UpdateProjectQuotas(BaseDelegateAPI):
    """
    The OpenStack endpoint to update the quota of a project in
    one or more regions
    """

    url = r"^openstack/quotas/?$"

    task_type = "update_quota"

    _number_of_returned_tasks = 5

    def get_active_quota_tasks(self):
        # Get the 5 last quota tasks.
        task_list = models.Task.objects.filter(
            task_type__exact=self.task_type,
            project_id__exact=self.project_id,
            cancelled=0,
        ).order_by("-created_on")[: self._number_of_returned_tasks]

        response_tasks = []

        for task in task_list:
            status = "Awaiting Approval"
            if task.completed:
                status = "Completed"

            task_data = {}
            for action in task.actions:
                task_data.update(action.action_data)
            new_dict = {
                "id": task.uuid,
                "regions": task_data["regions"],
                "size": task_data["size"],
                "request_user": task.keystone_user["username"],
                "task_created": task.created_on,
                "valid": all([a.valid for a in task.actions]),
                "status": status,
            }
            response_tasks.append(new_dict)

        return response_tasks

    def check_region_exists(self, region):
        # Check that the region actually exists
        id_manager = user_store.IdentityManager()
        v_region = id_manager.get_region(region)
        if not v_region:
            return False
        return True

    @utils.mod_or_admin
    def get(self, request):
        """
        This endpoint returns data about what sizes are available
        as well as the current status of a specified region's quotas.
        """

        quota_sizes = CONF.quota.sizes
        size_order = CONF.quota.sizes_ascending

        self.project_id = request.keystone_user["project_id"]
        regions = request.query_params.get("regions", None)
        include_usage = request.query_params.get("include_usage", True)

        if regions:
            regions = regions.split(",")
        else:
            id_manager = user_store.IdentityManager()
            # Only get the region id as that is what will be passed from
            # parameters otherwise
            regions = (region.id for region in id_manager.list_regions())

        region_quotas = []

        quota_manager = QuotaManager(self.project_id)
        for region in regions:
            if self.check_region_exists(region):
                region_quotas.append(
                    quota_manager.get_region_quota_data(region, include_usage)
                )
            else:
                return Response({"ERROR": ["Region: %s is not valid" % region]}, 400)

        response_tasks = self.get_active_quota_tasks()

        return Response(
            {
                "regions": region_quotas,
                "quota_sizes": quota_sizes,
                "quota_size_order": size_order,
                "active_quota_tasks": response_tasks,
            }
        )

    @utils.mod_or_admin
    def post(self, request):

        request.data["project_id"] = request.keystone_user["project_id"]
        self.project_id = request.keystone_user["project_id"]

        regions = request.data.get("regions", None)

        if not regions:
            id_manager = user_store.IdentityManager()
            regions = [region.id for region in id_manager.list_regions()]
            request.data["regions"] = regions

        self.logger.info("(%s) - New UpdateProjectQuotas request." % timezone.now())

        self.task_manager.create_from_request(self.task_type, request)

        return Response({"notes": ["task created"]}, status=202)
