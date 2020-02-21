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

from adjutant import exceptions
from adjutant.api import utils
from adjutant.api.v1.base import BaseDelegateAPI


# NOTE(adriant): We should deprecate these Views properly and switch tests
# to work against the openstack ones.


class CreateProjectAndUser(BaseDelegateAPI):

    url = r"^actions/CreateProjectAndUser/?$"

    config_group = groups.DynamicNameConfigGroup(
        children=[
            fields.StrConfig(
                "default_region",
                help_text="Default region in which any potential resources may be created.",
                required=True,
                default="RegionOne",
            ),
            fields.StrConfig(
                "default_domain_id",
                help_text="Domain in which project and users will be created.",
                default="default",
                required=True,
            ),
            fields.StrConfig(
                "default_parent_id",
                help_text="Parent id under which this project will be created. "
                "Default is None, and will create under default domain.",
                default=None,
            ),
        ]
    )

    task_type = "create_project_and_user"

    def post(self, request, format=None):
        """
        Unauthenticated endpoint bound primarily to NewProjectWithUser.

        This process requires approval, so this will validate
        incoming data and create a task to be approved
        later.
        """
        self.logger.info("(%s) - Starting new project task." % timezone.now())

        class_conf = self.config

        # we need to set the region the resources will be created in:
        request.data["region"] = class_conf.default_region

        # domain
        request.data["domain_id"] = class_conf.default_domain_id

        # parent_id for new project, if null defaults to domain:
        request.data["parent_id"] = class_conf.default_parent_id

        self.task_manager.create_from_request(self.task_type, request)

        return Response({"notes": ["task created"]}, status=202)


class InviteUser(BaseDelegateAPI):

    url = r"^actions/InviteUser/?$"

    task_type = "invite_user_to_project"

    @utils.mod_or_admin
    def get(self, request):
        return super(InviteUser, self).get(request)

    @utils.mod_or_admin
    def post(self, request, format=None):
        """
        Invites a user to the current tenant.

        This endpoint requires either Admin access or the
        request to come from a project_admin|project_mod.
        As such this Task is considered pre-approved.
        """
        self.logger.info("(%s) - New AttachUser request." % timezone.now())

        # Default project_id to the keystone user's project
        if "project_id" not in request.data or request.data["project_id"] is None:
            request.data["project_id"] = request.keystone_user["project_id"]

        # Default domain_id to the keystone user's project
        if "domain_id" not in request.data or request.data["domain_id"] is None:
            request.data["domain_id"] = request.keystone_user["project_domain_id"]

        self.task_manager.create_from_request(self.task_type, request)

        return Response({"notes": ["task created"]}, status=202)


class ResetPassword(BaseDelegateAPI):

    url = r"^actions/ResetPassword/?$"

    task_type = "reset_user_password"

    @utils.minimal_duration(min_time=3)
    def post(self, request, format=None):
        """
        Unauthenticated endpoint bound to the password reset action.
        This will submit and approve a password reset request.
         ---
        parameters:
            - name: email
              required: true
              type: string
              description: The email of the user to reset
            - name: username
              required: false
              type: string
              description: The username of the user, not required if using
                           USERNAME_IS_PASSWORD

        responseMessages:
            - code: 400
              message: Validation Errors
            - code: 200
              message: Success. Does not indicate user exists.

        """
        self.logger.info("(%s) - New ResetUser request." % timezone.now())

        try:
            self.task_manager.create_from_request(self.task_type, request)
        except exceptions.BaseTaskException as e:
            self.logger.info(
                "(%s) - ResetPassword raised error: %s" % (timezone.now(), e)
            )

        response_dict = {
            "notes": ["If user with email exists, reset token will be issued."]
        }

        return Response(response_dict, status=202)


class EditUser(BaseDelegateAPI):

    url = r"^actions/EditUser/?$"

    task_type = "edit_user_roles"

    @utils.mod_or_admin
    def post(self, request, format=None):
        """
        This endpoint requires either mod access or the
        request to come from a project_admin.
        As such this Task is considered pre-approved.
        Runs process_actions, then does the approve step and
        approve validation, and creates a Token if valid.
        """
        self.logger.info("(%s) - New EditUser request." % timezone.now())

        self.task_manager.create_from_request(self.task_type, request)

        return Response({"notes": ["task created"]}, status=202)


class UpdateEmail(BaseDelegateAPI):

    url = r"^actions/UpdateEmail/?$"

    task_type = "update_user_email"

    @utils.authenticated
    def post(self, request, format=None):
        """
        Endpoint bound to the update email action.
        This will submit and approve an update email action.
        """

        request.data["user_id"] = request.keystone_user["user_id"]

        self.task_manager.create_from_request(self.task_type, request)

        return Response({"notes": ["task created"]}, status=202)
