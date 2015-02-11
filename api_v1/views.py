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

from decorator import decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from models import Registration, Token
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4

from django.conf import settings


@decorator
def admin_or_owner(func, *args, **kwargs):
    req_roles = {'admin', 'project_owner'}
    request = args[1]
    roles = set(request.keystone_user.get('roles', []))

    if roles & req_roles:
        return func(*args, **kwargs)

    return Response({'notes': ["Must have one of the following roles: %s" %
                               list(req_roles)]},
                    403)


@decorator
def admin(func, *args, **kwargs):
    request = args[1]
    roles = request.keystone_user.get('roles', [])
    if "admin" in roles:
        return func(*args, **kwargs)

    return Response({'notes': ["Must be admin."]},
                    403)


def create_token(registration):
    # expire needs to be made configurable.
    expire = timezone.now() + timedelta(hours=24)

    # is this a good way to create tokens?
    uuid = uuid4().hex
    token = Token.objects.create(
        registration=registration,
        token=uuid,
        expires=expire
    )
    token.save()


class RegistrationList(APIView):

    @admin
    def get(self, request, format=None):
        """A list of dict representations of Registration objects
           and their related actions."""
        registrations = Registration.objects.all()
        reg_list = []
        for registration in registrations:
            reg_list.append(registration.to_dict())
        return Response(reg_list)


class RegistrationDetail(APIView):

    @admin
    def get(self, request, uuid, format=None):
        """Dict representation of a Registration object
           and its related actions."""
        registration = Registration.objects.get(uuid=uuid)
        return Response(registration.to_dict())

    @admin
    def post(self, request, uuid, format=None):
        """Will approve the Registration specified,
           followed by running the post_approve actions
           and if valid will setup and create a related token. """
        if request.data.get('approved', False) is True:
            # TODO(adriant): Handle the NotFound case
            registration = Registration.objects.get(uuid=uuid)
            registration.approved = True

            need_token = False
            valid = True
            notes = registration.notes

            actions = []

            for action in registration.actions:
                act_model = action.get_action()
                actions.append(act_model)
                notes[unicode(act_model)] += act_model.post_approve()

                if not action.valid:
                    valid = False
                if action.need_token:
                    need_token = True

            registration.notes = notes
            registration.save()

            if valid:
                if need_token:
                    create_token(registration)
                    return Response({'notes': ['created token']}, status=200)
                else:
                    submit_notes = {}
                    for action in actions:
                        note = action.submit({})
                        notes[unicode(action)] += note
                        submit_notes[unicode(action)] = note

                    registration.notes = notes
                    registration.completed = True
                    registration.save()
                    return Response({'notes': submit_notes}, status=200)
            return Response({'notes': ['actions invalid']}, status=400)
        else:
            return Response({'approved': ["this field is required."]},
                            status=400)


class TokenList(APIView):
    """Admin functionality for managing/monitoring tokens."""

    @admin
    def get(self, request, format=None):
        """A list of dict representations of Token objects."""
        tokens = Token.objects.all()
        token_list = []
        for token in tokens:
            token_list.append(token.to_dict())
        return Response(token_list)


class TokenDetail(APIView):

    def get(self, request, id, format=None):
        """Returns a response with the list of required fields
           and what actions those go towards."""
        token = Token.objects.get(token=id)

        if token.expires < timezone.now():
            return Response({'notes': ['This token has expired.']}, status=400)

        required_fields = []
        actions = []

        for action in token.registration.actions:
            action = action.get_action()
            actions.append(action)
            for field in action.token_fields:
                if field not in required_fields:
                    required_fields.append(field)

        return Response({'actions': [unicode(act) for act in actions],
                         'required_fields': required_fields})

    def post(self, request, id, format=None):
        """Ensures the required fields are present,
           will then pass those to the actions via the submit
           function."""

        token = Token.objects.get(token=id)

        if token.expires < timezone.now():
            return Response({'notes': ['This token has expired.']}, status=400)

        required_fields = set()
        actions = []

        for action in token.registration.actions:
            action = action.get_action()
            actions.append(action)
            for field in action.token_fields:
                required_fields.add(field)

        errors = {}
        data = {}

        for field in required_fields:
            try:
                data[field] = request.data[field]
            except KeyError:
                errors[field] = ["This field is required.", ]

        if errors:
            return Response(errors, status=400)

        try:
            notes = token.registration.notes
            tk_notes = {}
            for action in actions:
                note = action.submit(data)
                notes[unicode(action)] += note
                tk_notes[unicode(action)] = note
            token.registration.completed = True
            token.registration.notes = notes
            token.registration.save()
            token.delete()

            return Response({'notes': tk_notes}, status=200)
        except KeyError:
            pass


class ActionView(APIView):
    """Base class for api calls that start a Registration.
       Until it is moved to settings, 'default_action' is a
       required hardcoded field."""

    def get(self, request):
        actions = [self.default_action, ]

        actions += settings.API_ACTIONS.get(self.__class__.__name__, [])

        required_fields = []

        for action in actions:
            action_class, action_serializer = settings.ACTION_CLASSES[action]
            for field in action_class.required:
                if field not in required_fields:
                    required_fields.append(field)

        return Response({'actions': actions,
                         'required_fields': required_fields})

    def process_actions(self, request):
        """Will ensure the request data contains the required data
           based on the action serializer, and if present will create
           a Registration and the linked actions, attaching notes
           based on running of the the pre_approve validation
           function on all the actions."""

        actions = [self.default_action, ]

        actions += settings.API_ACTIONS.get(self.__class__.__name__, [])

        act_list = []

        valid = True
        for action in actions:
            action_class, action_serializer = settings.ACTION_CLASSES[action]

            if action_serializer is not None:
                serializer = action_serializer(data=request.data)
            else:
                serializer = None

            act_list.append({
                'name': action,
                'action': action_class,
                'serializer': serializer})

            if serializer is not None and not serializer.is_valid():
                valid = False

        if valid:
            ip_addr = request.META['REMOTE_ADDR']
            keystone_user = request.keystone_user

            registration = Registration.objects.create(
                reg_ip=ip_addr, keystone_user=keystone_user)
            registration.save()

            notes = {}
            for i, act in enumerate(act_list):
                if act['serializer'] is not None:
                    data = act['serializer'].validated_data
                else:
                    data = {}
                action = act['action'](
                    data=data, registration=registration,
                    order=i
                )

                notes[act['name']] = action.pre_approve()

            registration.notes = notes
            registration.save()
            return {'registration': registration,
                    'notes': notes}
        else:
            errors = {}
            for act in act_list:
                if act['serializer'] is not None:
                    errors.update(act['serializer'].errors)
            return {'errors': errors}

    def approve(self, registration):
        registration.approved = True

        action_models = registration.actions
        actions = []

        valid = True
        need_token = False
        for action in action_models:
            act = action.get_action()
            actions.append(act)

            if not act.valid:
                valid = False

        if valid:
            notes = registration.notes

            for action in actions:
                notes[unicode(action)] += action.post_approve()

                if not action.valid:
                    valid = False
                if action.need_token:
                    need_token = True

            registration.notes = notes
            registration.save()

            if valid:
                if need_token:
                    create_token(registration)
                    return Response({'notes': ['created token']}, status=200)
                else:
                    for action in actions:
                        notes[unicode(action)] += [action.submit({}), ]

                    registration.notes = notes
                    registration.completed = True
                    registration.save()
                    return Response({'notes': notes}, status=200)
            return Response({'notes': ['actions invalid']}, status=400)
        return Response({'notes': ['actions invalid']}, status=400)


class CreateProject(ActionView):

    default_action = "NewProject"

    def post(self, request, format=None):
        """Runs internal process_actions and sends back notes or errors."""
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            return Response(errors, status=400)

        return Response({'notes': ['registration created']}, status=200)


class AttachUser(ActionView):

    default_action = 'NewUser'

    @admin_or_owner
    def get(self, request):
        return super(AttachUser, self).get(request)

    @admin_or_owner
    def post(self, request, format=None):
        """This endpoint requires either Admin access or the
           request to come from a project_owner.
           As such this Registration is considered pre-approved.
           Runs process_actions, then does the approve and
           post_approve validation, and creates a Token if valid."""
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            return Response(errors, status=400)

        registration = processed['registration']

        return self.approve(registration)


class ResetPassword(ActionView):

    default_action = 'ResetUser'

    def post(self, request, format=None):
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            return Response(errors, status=400)

        registration = processed['registration']

        return self.approve(registration)
