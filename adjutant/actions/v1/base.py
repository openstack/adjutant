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

from logging import getLogger

from django.utils import timezone

from adjutant.config import CONF
from adjutant.common.quota import QuotaManager
from adjutant.common import user_store
from adjutant.common.utils import str_datetime
from adjutant.actions.models import Action


class BaseAction(object):
    """
    Base class for the object wrapping around the database model.
    Setup to allow multiple action types and different internal logic
    per type but built from a single database type.
    - 'required' defines what fields to setup from the data.

    If need_token MAY be true, you must implement '_token_email',
    which should return the email the action wants the token sent to.
    While there are checks to prevent duplicates or different emails,
    try and only have one action in your chain provide the email.

    The Action can do anything it needs at one of the three functions
    called by the views:
    - 'prepare'
    - 'approve'
    - 'submit'

    All logic and validation should be handled within the action itself,
    and any other actions it is linked to. The way in which prepare,
    approve, and submit are called should rarely change. Actions should
    be built with those steps in mind, thinking about what they mean,
    and when they execute.

    By using 'get_cache' and 'set_cache' they can pass data along which
    may be needed by the action later. This cache is backed to the database.

    Passing data along to other actions is done via the task and
    its cache, but this is in memory only, so it is only useful during the
    same action stage ('prepare', 'approve', etc.).

    Other than the task cache, actions should not be altering database
    models other than themselves. This is not enforced, just a guideline.
    """

    required = []

    serializer = None

    config_group = None

    def __init__(self, data, action_model=None, task=None, order=None):
        """
        Build itself around an existing database model,
        or build itself and creates a new database model.
        Sets up required data as fields.
        """

        self.logger = getLogger("adjutant")

        for field in self.required:
            field_data = data[field]
            setattr(self, field, field_data)

        if action_model:
            self.action = action_model
        else:
            # make new model and save in db
            action = Action.objects.create(
                action_name=self.__class__.__name__,
                action_data=data,
                task=task,
                order=order,
            )
            action.save()
            self.action = action

        # NOTE(adriant): override this since we don't need the group
        #                beyond registration.
        self.config_group = None
        self._config = None

    @property
    def valid(self):
        return self.action.valid

    @property
    def need_token(self):
        return self.action.need_token

    def get_email(self):
        return self._get_email()

    def _get_email(self):
        return None

    def get_cache(self, key):
        return self.action.cache.get(key, None)

    def set_cache(self, key, value):
        self.action.cache[key] = value
        self.action.save()

    @property
    def token_fields(self):
        return self.action.cache.get("token_fields", [])

    def set_token_fields(self, token_fields):
        self.action.cache["token_fields"] = token_fields
        self.action.save()

    @property
    def auto_approve(self):
        return self.action.auto_approve

    def set_auto_approve(self, can_approve=True):
        self.add_note("Auto approve set to %s." % can_approve)
        self.action.auto_approve = can_approve
        self.action.save()

    def add_note(self, note):
        """
        Logs the note, and also adds it to the task action notes.
        """
        now = timezone.now()
        self.logger.info("(%s) - %s" % (now, note))
        note = "%s - (%s)" % (note, now)
        self.action.task.add_action_note(str(self), note)

    @property
    def config(self):
        """Get my config.

        Returns a config_group of the config for this action.
        """
        if self._config is not None:
            return self._config

        try:
            action_defaults = CONF.workflow.action_defaults.get(self.__class__.__name__)
        except KeyError:
            self._config = {}
            return self._config

        try:
            task_conf = CONF.workflow.tasks[self.action.task.task_type]
            self._config = action_defaults.overlay(
                task_conf.actions[self.__class__.__name__]
            )
        except KeyError:
            self._config = action_defaults
        return self._config

    def prepare(self):
        try:
            return self._prepare()
        except NotImplementedError:
            self.logger.warning(
                "DEPRECATED: Action '_pre_approve' stage has been renamed "
                "to 'prepare'."
            )
            return self._pre_approve()

    def approve(self):
        try:
            return self._approve()
        except NotImplementedError:
            self.logger.warning(
                "DEPRECATED: Action '_post_approve' stage has been renamed "
                "to 'prepare'."
            )
            return self._post_approve()

    def submit(self, token_data, keystone_user=None):
        try:
            return self._submit(token_data, keystone_user)
        except TypeError:
            self.logger.warning(
                "DEPRECATED: Action '_submit' must accept a second parameter "
                "'keystone_user=None' along with the required 'token_data'."
            )
            return self._submit(token_data)

    def _prepare(self):
        raise NotImplementedError

    def _approve(self):
        raise NotImplementedError

    def _submit(self, token_data, keystone_user=None):
        raise NotImplementedError

    def __str__(self):
        return self.__class__.__name__


class ResourceMixin(object):
    """Base Mixin class for dealing with Openstack resources."""

    def _validate_keystone_user_project_id(self):
        keystone_user = self.action.task.keystone_user

        if keystone_user["project_id"] != self.project_id:
            self.add_note("Project id does not match keystone user project.")
            return False
        return True

    def _validate_keystone_user_domain_id(self):
        keystone_user = self.action.task.keystone_user

        if keystone_user["project_domain_id"] != self.domain_id:
            self.add_note("Domain id does not match keystone user domain.")
            return False
        return True

    def _validate_domain_id(self):
        id_manager = user_store.IdentityManager()
        domain = id_manager.get_domain(self.domain_id)
        if not domain:
            self.add_note("Domain does not exist.")
            return False

        return True

    def _validate_project_id(self):
        # Handle an edge_case where some actions set their
        # own project_id value.
        if not self.project_id:
            self.add_note("No project_id given.")
            return False

        # Now actually check the project exists.
        id_manager = user_store.IdentityManager()
        project = id_manager.get_project(self.project_id)
        if not project:
            self.add_note("Project with id %s does not exist." % self.project_id)
            return False
        self.add_note("Project with id %s exists." % self.project_id)
        return True

    def _validate_domain_name(self):
        id_manager = user_store.IdentityManager()
        self.domain = id_manager.find_domain(self.domain_name)
        if not self.domain:
            self.add_note("Domain does not exist.")
            return False
        # also store the domain_id separately for later use
        self.domain_id = self.domain.id
        return True

    def _validate_region_exists(self, region):
        # Check that the region actually exists
        id_manager = user_store.IdentityManager()
        v_region = id_manager.get_region(region)
        if not v_region:
            self.add_note("ERROR: Region: %s does not exist." % region)
            return False
        self.add_note("Region: %s exists." % region)

        return True


class UserMixin(ResourceMixin):
    """Mixin with functions for users."""

    # Accessors
    def _validate_username_exists(self):
        id_manager = user_store.IdentityManager()

        self.user = id_manager.find_user(self.username, self.domain.id)
        if not self.user:
            self.add_note("No user present with username")
            return False
        return True

    def _validate_role_permissions(self):
        keystone_user = self.action.task.keystone_user
        # Role permissions check
        requested_roles = set(list(self.roles) + list(self.inherited_roles))
        if not self.are_roles_manageable(
            user_roles=keystone_user["roles"], requested_roles=requested_roles
        ):
            self.add_note("User does not have permission to edit role(s).")
            return False
        return True

    def are_roles_manageable(self, user_roles=None, requested_roles=None):
        if user_roles is None:
            user_roles = []
        if requested_roles is None:
            requested_roles = []

        requested_roles = set(requested_roles)
        # blacklist checks
        blacklisted_roles = set(["admin"])
        if len(blacklisted_roles & requested_roles) > 0:
            return False

        # user manageable role
        id_manager = user_store.IdentityManager()
        manageable_roles = id_manager.get_manageable_roles(user_roles)
        intersection = set(manageable_roles) & requested_roles
        # if all requested roles match, we can proceed
        return intersection == requested_roles

    def find_user(self):
        id_manager = user_store.IdentityManager()
        return id_manager.find_user(self.username, self.domain_id)

    # Mutators
    def grant_roles(self, user, roles, project_id, inherited=False):
        return self._user_roles_edit(
            user, roles, project_id, remove=False, inherited=inherited
        )

    def remove_roles(self, user, roles, project_id, inherited=False):
        return self._user_roles_edit(
            user, roles, project_id, remove=True, inherited=inherited
        )

    # Helper function to add or remove roles
    def _user_roles_edit(self, user, roles, project_id, remove=False, inherited=False):
        id_manager = user_store.IdentityManager()
        if not remove:
            action_fn = id_manager.add_user_role
            action_string = "granting"
        else:
            action_fn = id_manager.remove_user_role
            action_string = "removing"
        ks_roles = []
        try:
            for role in roles:
                ks_role = id_manager.find_role(role)
                if ks_role:
                    ks_roles.append(ks_role)
                else:
                    raise TypeError("Keystone missing role: %s" % role)

            for role in ks_roles:
                action_fn(user, role, project_id, inherited=inherited)
        except Exception as e:
            self.add_note(
                "Error: '%s' while %s the roles: %s on user: %s "
                % (e, action_string, roles, user)
            )
            raise

    def enable_user(self, user=None):
        id_manager = user_store.IdentityManager()
        try:
            if not user:
                user = self.find_user()
            id_manager.enable_user(user)
        except Exception as e:
            self.add_note(
                "Error: '%s' while re-enabling user: %s with roles: %s"
                % (e, self.username, self.roles)
            )
            raise

    def create_user(self, password):
        id_manager = user_store.IdentityManager()
        try:
            user = id_manager.create_user(
                name=self.username,
                password=password,
                email=self.email,
                domain=self.domain_id,
                created_on=str_datetime(timezone.now()),
            )
        except Exception as e:
            # TODO: Narrow the Exceptions caught to a relevant set.
            self.add_note(
                "Error: '%s' while creating user: %s with roles: %s"
                % (e, self.username, self.roles)
            )
            raise
        return user

    def update_password(self, password, user=None):
        id_manager = user_store.IdentityManager()
        try:
            if not user:
                user = self.find_user()
            id_manager.update_user_password(user, password)
        except Exception as e:
            self.add_note(
                "Error: '%s' while changing password for user: %s" % (e, self.username)
            )
            raise

    def update_email(self, email, user=None):
        id_manager = user_store.IdentityManager()
        try:
            if not user:
                user = self.find_user()
            id_manager.update_user_email(user, email)
        except Exception as e:
            self.add_note(
                "Error: '%s' while changing email for user: %s" % (e, self.username)
            )
            raise

    def update_user_name(self, username, user=None):
        id_manager = user_store.IdentityManager()
        try:
            if not user:
                user = self.find_user()
            id_manager.update_user_name(user, username)
        except Exception as e:
            self.add_note(
                "Error: '%s' while changing username for user: %s" % (e, self.username)
            )
            raise


class ProjectMixin(ResourceMixin):
    """Mixin with functions for projects."""

    def _validate_parent_project(self):
        id_manager = user_store.IdentityManager()
        # NOTE(adriant): If parent id is None, Keystone defaults to the domain.
        # So we only care to validate if parent_id is not None.
        if self.parent_id:
            parent = id_manager.get_project(self.parent_id)
            if not parent:
                self.add_note("Parent id: '%s' does not exist." % self.parent_id)
                return False
        return True

    def _validate_project_absent(self):
        id_manager = user_store.IdentityManager()
        project = id_manager.find_project(self.project_name, self.domain_id)
        if project:
            self.add_note("Existing project with name '%s'." % self.project_name)
            return False

        self.add_note("No existing project with name '%s'." % self.project_name)
        return True

    def _create_project(self):
        id_manager = user_store.IdentityManager()
        description = getattr(self, "description", "")
        try:
            project = id_manager.create_project(
                self.project_name,
                created_on=str_datetime(timezone.now()),
                parent=self.parent_id,
                domain=self.domain_id,
                description=description,
            )
        except Exception as e:
            self.add_note(
                "Error: '%s' while creating project: %s" % (e, self.project_name)
            )
            raise
        # put project_id into action cache:
        self.action.task.cache["project_id"] = project.id
        self.set_cache("project_id", project.id)
        self.add_note("New project '%s' created." % project.name)


class QuotaMixin(ResourceMixin):
    """Mixin with functions for dealing with quotas and limits."""

    def _region_usage_greater_than_quota(self, usage, quota):
        for service, values in quota.items():
            for resource, value in values.items():
                try:
                    if usage[service][resource] > value and value >= 0:
                        return True
                except KeyError:
                    pass
        return False

    def _usage_greater_than_quota(self, regions):
        quota_manager = QuotaManager(
            self.project_id,
            size_difference_threshold=self.config.size_difference_threshold,
        )
        quota = CONF.quota.sizes.get(self.size, {})
        for region in regions:
            current_usage = quota_manager.get_current_usage(region)
            if self._region_usage_greater_than_quota(current_usage, quota):
                return True
        return False

    def _validate_regions_exist(self):
        # Check that all the regions in the list exist
        for region in self.regions:
            if not self._validate_region_exists(region):
                return False
        return True

    def _validate_usage_lower_than_quota(self):
        if self._usage_greater_than_quota(self.regions):
            self.add_note("Current usage greater than new quota")
            return False
        return True


class UserIdAction(BaseAction):
    def _get_target_user(self):
        """
        Gets the target user by id
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(self.user_id)

        return user


class UserNameAction(BaseAction):
    """
    Base action for dealing with users. Removes username if
    USERNAME_IS_EMAIL and sets email to be username.
    """

    def __init__(self, *args, **kwargs):
        if CONF.identity.username_is_email:
            # NOTE(amelia): Make a copy to avoid editing it globally.
            self.required = list(self.required)
            try:
                self.required.remove("username")
            except ValueError:
                pass
                # nothing to remove
            super(UserNameAction, self).__init__(*args, **kwargs)
            self.username = self.email
        else:
            super(UserNameAction, self).__init__(*args, **kwargs)

    def _get_email(self):
        return self.email

    def _get_target_user(self):
        """
        Gets the target user by their username
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.find_user(self.username, self.domain_id)

        return user
