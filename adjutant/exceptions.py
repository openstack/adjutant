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

from rest_framework import status


class BaseServiceException(Exception):
    """Configuration, or core service logic has had an error

    This is an internal only exception and should only be thrown
    when and error occurs that the user shouldn't see.

    If thrown during the course of an API call will be caught and returned
    to the user as an ServiceUnavailable error with a 503 response.
    """

    default_message = "A internal service error has occured."

    def __init__(self, message=None):
        self.message = message

    def __str__(self):
        return self.message or self.default_message


class InvalidActionClass(BaseServiceException):
    default_message = "Cannot register action not built off the BaseAction class."


class InvalidActionSerializer(BaseServiceException):
    default_message = "Action serializer must be a valid DRF serializer."


class InvalidTaskClass(BaseServiceException):
    default_message = "Action serializer must be a valid DRF serializer."


class InvalidAPIClass(BaseServiceException):
    default_message = "Cannot register task not built off the BaseTask class."


class DelegateAPINotRegistered(BaseServiceException):
    default_message = "Failed to setup DelegateAPI that has not been registered."


class TaskNotRegistered(BaseServiceException):
    default_message = "Failed to setup Task that has not been registered."


class ActionNotRegistered(BaseServiceException):
    default_message = "Failed to setup Action that has not been registered."


class SerializerMissingException(BaseServiceException):
    default_message = "Serializer configured but it does not exist."


class ConfigurationException(BaseServiceException):
    default_message = "Missing or incorrect configuration value."


class BaseAPIException(Exception):
    """An Task error occurred."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message=None, internal_message=None):
        if message:
            self.message = message
        else:
            self.message = self.default_message
        self.internal_message = internal_message

    def __str__(self):
        message = ""
        if self.internal_message:
            message = "%s - " % self.internal_message
        message += str(self.message)
        return message


class NotFound(BaseAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Not found."


class TaskNotFound(NotFound):
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Task not found."


class ServiceUnavailable(BaseAPIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "Service temporarily unavailable, try again later."


class TaskSerializersInvalid(BaseAPIException):
    default_message = "Data passed to the Task was invalid."


class TaskDuplicateFound(BaseAPIException):
    default_message = "This Task already exists."
    status_code = status.HTTP_409_CONFLICT


class BaseTaskException(BaseAPIException):
    default_message = "An Task error occurred."
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, task, message=None, internal_message=None):
        super(BaseTaskException, self).__init__(message, internal_message)
        self.task = task

    def __str__(self):
        message = "%s (%s) - " % (self.task.task_type, self.task.uuid)
        message += super(BaseTaskException, self).__str__()
        return message


class TaskTokenSerializersInvalid(BaseTaskException):
    default_message = "Data passed for the Task token was invalid."


class TaskActionsInvalid(BaseTaskException):
    default_message = "One or more of the Task actions was invalid."


class TaskStateInvalid(BaseTaskException):
    default_message = "Action does is not possible on task in current state."


class TaskActionsFailed(BaseTaskException):
    """For use when Task processing fails and we want to wrap that."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "Service temporarily unavailable, try again later."
