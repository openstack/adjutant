# Copyright (C) 2019 Catalyst Cloud Ltd
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

import hashlib
from logging import getLogger

from confspirator import groups
from confspirator import fields

from adjutant import actions as adj_actions
from adjutant.api.models import Task
from adjutant.config import CONF
from django.utils import timezone
from adjutant.notifications.utils import create_notification
from adjutant.tasks.v1.utils import send_stage_email, create_token, handle_task_error
from adjutant import exceptions


def make_task_config(task_class):

    config_group = groups.DynamicNameConfigGroup()
    config_group.register_child_config(
        fields.BoolConfig(
            "allow_auto_approve",
            help_text="Override if this task allows auto_approval. "
            "Otherwise uses task default.",
            default=task_class.allow_auto_approve,
        )
    )
    config_group.register_child_config(
        fields.ListConfig(
            "additional_actions",
            help_text="Additional actions to be run as part of the task "
            "after default actions.",
            default=task_class.additional_actions or [],
        )
    )
    config_group.register_child_config(
        fields.IntConfig(
            "token_expiry",
            help_text="Override for the task token expiry. "
            "Otherwise uses task default.",
            default=task_class.token_expiry,
        )
    )
    config_group.register_child_config(
        fields.DictConfig(
            "actions",
            help_text="Action config overrides over the action defaults. "
            "See 'adjutant.workflow.action_defaults'.",
            is_json=True,
            default=task_class.action_config or {},
            sample_default={
                "SomeCustomAction": {"some_action_setting": "<a-uuid-probably>"}
            },
        )
    )
    config_group.register_child_config(
        fields.DictConfig(
            "emails",
            help_text="Email config overrides for this task over task defaults."
            "See 'adjutant.workflow.emails'.",
            is_json=True,
            default=task_class.email_config or {},
            sample_default={
                "initial": None,
                "token": {
                    "subject": "Some custom subject",
                },
            },
        )
    )
    config_group.register_child_config(
        fields.DictConfig(
            "notifications",
            help_text="Notification config overrides for this task over task defaults."
            "See 'adjutant.workflow.notifications'.",
            is_json=True,
            default=task_class.notification_config or {},
            sample_default={
                "standard_handlers": ["EmailNotification"],
                "error_handlers": ["EmailNotification"],
                "standard_handler_config": {
                    "EmailNotification": {
                        "emails": ["example@example.com"],
                        "reply": "no-reply@example.com",
                    }
                },
                "error_handler_config": {
                    "EmailNotification": {
                        "emails": ["example@example.com"],
                        "reply": "no-reply@example.com",
                    }
                },
            },
        )
    )
    return config_group


class BaseTask(object):
    """
    Base class for in memory task representation.

    This serves as the internal task logic handler, and is used to
    define what a task looks like.

    Most of the time this class shouldn't be called or used directly
    as the task manager is what handles the direct interaction to the
    logic here, and includes some wrapper logic to help deal with workflows.
    """

    # required values in custom task
    task_type = None
    default_actions = None

    # default values to optionally override in task definition
    deprecated_task_types = None
    duplicate_policy = "cancel"
    send_approval_notification = True
    token_requires_authentication = False

    # config defaults for the task (used to generate default config):
    allow_auto_approve = True
    additional_actions = None
    token_expiry = None
    action_config = None
    email_config = None
    notification_config = None

    def __init__(self, task_model=None, task_data=None, action_data=None):
        self._config = None
        self.logger = getLogger("adjutant")

        if task_model:
            self.task = task_model
            self._refresh_actions()
        else:
            # raises 400 validation error
            action_serializer_list = self._instantiate_action_serializers(action_data)

            hash_key = self._create_task_hash(action_serializer_list)
            # raises duplicate error
            self._handle_duplicates(hash_key)

            keystone_user = task_data.get("keystone_user", {})
            self.task = Task.objects.create(
                keystone_user=keystone_user,
                project_id=keystone_user.get("project_id"),
                task_type=self.task_type,
                hash_key=hash_key,
            )
            self.task.save()

            # Instantiate actions with serializers
            self.actions = []
            for i, action in enumerate(action_serializer_list):
                data = action["serializer"].validated_data

                # construct the action class
                self.actions.append(
                    action["action"](data=data, task=self.task, order=i)
                )
            self.logger.info(
                "(%s) - '%s' task created (%s)."
                % (timezone.now(), self.task_type, self.task.uuid)
            )

    def _instantiate_action_serializers(self, action_data, use_existing_actions=False):
        action_serializer_list = []

        if use_existing_actions:
            actions = self.actions
        else:
            actions = self.default_actions[:]
            actions += self.config.additional_actions

        # instantiate all action serializers and check validity
        valid = True
        for action in actions:
            if use_existing_actions:
                action_name = action.action.action_name
            else:
                action_name = action

            action_class = adj_actions.ACTION_CLASSES[action_name]

            if use_existing_actions:
                action_class = action

            # instantiate serializer class
            if not action_class.serializer:
                raise exceptions.SerializerMissingException(
                    "No serializer defined for action %s" % action_name
                )
            serializer = action_class.serializer(data=action_data)

            action_serializer_list.append(
                {"name": action_name, "action": action_class, "serializer": serializer}
            )

            if serializer and not serializer.is_valid():
                valid = False

        if not valid:
            errors = {}
            for action in action_serializer_list:
                if action["serializer"]:
                    errors.update(action["serializer"].errors)
            raise exceptions.TaskSerializersInvalid(errors)

        return action_serializer_list

    def _create_task_hash(self, action_list):
        hashable_list = [
            self.task_type,
        ]

        for action in action_list:
            hashable_list.append(action["name"])
            if not action["serializer"]:
                continue
            # iterate like this to maintain consistent order for hash
            fields = sorted(action["serializer"].validated_data.keys())
            for field in fields:
                try:
                    hashable_list.append(action["serializer"].validated_data[field])
                except KeyError:
                    if field == "username" and CONF.identity.username_is_email:
                        continue
                    else:
                        raise

        return hashlib.sha256(str(hashable_list).encode("utf-8")).hexdigest()

    def _handle_duplicates(self, hash_key):

        duplicate_tasks = Task.objects.filter(
            hash_key=hash_key, completed=0, cancelled=0
        )

        if not duplicate_tasks:
            return

        if self.duplicate_policy == "cancel":
            now = timezone.now()
            self.logger.info("(%s) - Task is a duplicate - Cancelling old tasks." % now)
            for task in duplicate_tasks:
                task.add_task_note(
                    "Task cancelled because was an old duplicate. - (%s)" % now
                )
                task.get_task().cancel()
            return

        raise exceptions.TaskDuplicateFound()

    def _refresh_actions(self):
        self.actions = [a.get_action() for a in self.task.actions]

    def _create_token(self):
        self.clear_tokens()
        token_expiry = self.config.token_expiry or self.token_expiry
        token = create_token(self.task, token_expiry)
        self.add_note("Token created for task.")
        try:
            # will throw a key error if the token template has not
            # been specified
            email_conf = self.config.emails.token
            send_stage_email(self.task, email_conf, token)
        except KeyError as e:
            handle_task_error(e, self.task, error_text="while sending token")

    def add_note(self, note):
        """
        Logs the note, and also adds it to the task notes.
        """
        now = timezone.now()
        self.logger.info(
            "(%s)(%s)(%s) - %s" % (now, self.task_type, self.task.uuid, note)
        )
        note = "%s - (%s)" % (note, now)
        self.task.add_task_note(note)

    @property
    def config(self):
        """Get my config.

        Returns a dict of the config for this task.
        """
        if self._config is None:
            try:
                task_conf = CONF.workflow.tasks[self.task_type]
            except KeyError:
                task_conf = {}
            self._config = CONF.workflow.task_defaults.overlay(task_conf)
        return self._config

    def is_valid(self, internal_message=None):
        self._refresh_actions()
        valid = all([act.valid for act in self.actions])
        if not valid:
            # TODO(amelia): get action invalidation reasons and raise those
            raise exceptions.TaskActionsInvalid(
                self.task, "actions invalid", internal_message
            )

    @property
    def approved(self):
        return self.task.approved

    @property
    def completed(self):
        return self.task.completed

    @property
    def cancelled(self):
        return self.task.cancelled

    def confirm_state(self, approved=None, completed=None, cancelled=None):
        """Check that the Task is in a given state.

        None value means state is ignored. Otherwise expects true or false.
        """
        if completed is not None:
            if self.task.completed and not completed:
                raise exceptions.TaskStateInvalid(
                    self.task, "This task has already been completed."
                )
            if not self.task.completed and completed:
                raise exceptions.TaskStateInvalid(
                    self.task, "This task hasn't been completed."
                )

        if cancelled is not None:
            if self.task.cancelled and not cancelled:
                raise exceptions.TaskStateInvalid(
                    self.task, "This task has been cancelled."
                )
            if not self.task.cancelled and cancelled:
                raise exceptions.TaskStateInvalid(
                    self.task, "This task has not been cancelled."
                )
        if approved is not None:
            if self.task.approved and not approved:
                raise exceptions.TaskStateInvalid(
                    self.task, "This task has already been approved."
                )
            if not self.task.approved and approved:
                raise exceptions.TaskStateInvalid(
                    self.task, "This task has not been approved."
                )

    def update(self, action_data):
        self.confirm_state(approved=False, completed=False, cancelled=False)

        action_serializer_list = self._instantiate_action_serializers(
            action_data, use_existing_actions=True
        )

        hash_key = self._create_task_hash(action_serializer_list)
        self._handle_duplicates(hash_key)

        for action in action_serializer_list:
            data = action["serializer"].validated_data

            action["action"].action.action_data = data
            action["action"].action.save()
        self._refresh_actions()
        self.prepare()

    def prepare(self):
        """Run the prepare stage for all the actions.

        If the task can be auto approved, this will also run the approve
        stage.
        """

        self.confirm_state(approved=False, completed=False, cancelled=False)

        for action in self.actions:
            try:
                action.prepare()
            except Exception as e:
                handle_task_error(e, self.task, error_text="while setting up task")

        # send initial confirmation email:
        email_conf = self.config.emails.initial
        send_stage_email(self.task, email_conf)

        approve_list = [act.auto_approve for act in self.actions]

        # TODO(amelia): It would be nice to explicitly test this, however
        #               currently we don't have the right combinations of
        #               actions to allow for it.
        if False in approve_list:
            can_auto_approve = False
        elif True in approve_list:
            can_auto_approve = True
        else:
            can_auto_approve = False

        if self.config.allow_auto_approve is not None:
            allow_auto_approve = self.config.allow_auto_approve
        else:
            allow_auto_approve = self.allow_auto_approve

        if can_auto_approve and not allow_auto_approve:
            self.add_note("Actions allow auto aproval, but task does not.")
        elif can_auto_approve:
            self.add_note("Action allow auto approval. Auto approving.")
            self.approve()
            return

        if self.send_approval_notification:
            notes = {"notes": ["'%s' task needs approval." % self.task_type]}
            create_notification(self.task, notes)

    def approve(self, approved_by="system"):
        """Run the approve stage for all the actions."""

        self.confirm_state(completed=False, cancelled=False)

        self.is_valid("task invalid before approval")

        # We approve the task before running actions,
        # that way if something goes wrong we know if it was approved,
        # when it was approved, and who approved it.
        self.task.approved = True
        self.task.approved_on = timezone.now()
        self.task.approved_by = approved_by
        self.task.save()

        # approve all actions
        for action in self.actions:
            try:
                action.approve()
            except Exception as e:
                handle_task_error(e, self.task, error_text="while approving task")

        self.is_valid("task invalid after approval")

        need_token = any([act.need_token for act in self.actions])
        if need_token:
            self._create_token()
        else:
            self.submit()

    def reissue_token(self):
        self.confirm_state(approved=True, completed=False, cancelled=False)

        need_token = any([act.need_token for act in self.actions])
        if need_token:
            self._create_token()

    def clear_tokens(self):
        for token in self.task.tokens:
            token.delete()

    def submit(self, token_data=None, keystone_user=None):

        self.confirm_state(approved=True, completed=False, cancelled=False)

        required_fields = set()
        actions = []
        for action in self.task.actions:
            a = action.get_action()
            actions.append(a)
            for field in a.token_fields:
                required_fields.add(field)

        if not token_data:
            token_data = {}

        errors = {}
        data = {}

        for field in required_fields:
            try:
                data[field] = token_data[field]
            except KeyError:
                errors[field] = [
                    "This field is required.",
                ]
            except TypeError:
                errors = ["Improperly formated json. " "Should be a key-value object."]
                break

        if errors:
            raise exceptions.TaskTokenSerializersInvalid(self.task, errors)

        self.is_valid("task invalid before submit")

        for action in actions:
            try:
                action.submit(data, keystone_user)
            except Exception as e:
                handle_task_error(e, self.task, "while submiting task")

        self.is_valid("task invalid after submit")

        self.task.completed = True
        self.task.completed_on = timezone.now()
        self.task.save()
        for token in self.task.tokens:
            token.delete()

        # Sending confirmation email:
        email_conf = self.config.emails.completed
        send_stage_email(self.task, email_conf)

    def cancel(self):
        self.confirm_state(completed=False, cancelled=False)
        self.clear_tokens()
        self.task.cancelled = True
        self.task.save()
