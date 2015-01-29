# from django.shortcuts import render
# from base.models import User, Tenant
# from models import Registration
from decorator import decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from models import Registration, Token
import json
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4

from django.conf import settings


@decorator
def admin_or_owner(func, *args, **kwargs):
    req_roles = ['admin', 'project_owner']
    request = args[1]
    roles = request.keystone_user.get('roles', [])
    has_role = False
    for role in roles:
        if role in req_roles:
            has_role = True
            break

    if has_role:
        return func(*args, **kwargs)

    return Response("Must have one of the following roles: %s" % req_roles,
                    403)


@decorator
def admin(func, *args, **kwargs):
    request = args[1]
    roles = request.keystone_user.get('roles', [])
    if "admin" in roles:
        return func(*args, **kwargs)

    return Response("Must be admin.",
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
           followed by running the post_approve ations
           and if valid will setup and create a related token. """
        if request.data.get('approved', False) is True:
            # TODO(adriant): Handle the NotFound case
            registration = Registration.objects.get(uuid=uuid)
            registration.approved = True

            need_token = False
            valid = True
            notes = json.loads(registration.notes)

            actions = []

            for action in registration.actions:
                act_model = action.get_action()
                actions.append(act_model)
                notes[act_model.__unicode__()] += act_model.post_approve()

                if not action.valid:
                    valid = False
                if action.need_token:
                    need_token = True

            registration.notes = json.dumps(notes)
            registration.save()

            if valid:
                if need_token:
                    create_token(registration)
                    return Response({'notes': ['created token']}, status=200)
                else:
                    for action in actions:
                        notes[action.__unicode__()] += [action.submit({}), ]

                    registration.notes = json.dumps(notes)
                    registration.completed = True
                    registration.save()

                return Response({'notes': notes}, status=200)
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

        required_fields = set()
        actions = []

        for action in token.registration.actions:
            action = action.get_action()
            actions.append(action)
            for field in action.token_fields:
                required_fields.add(field)

        return Response({'actions': [act.__unicode__() for act in actions],
                         'required_fields': required_fields})

    def post(self, request, id, format=None):
        """Ensures the required fields are present,
           will then pass those to the actions via the submit
           function."""

        token = Token.objects.get(token=id)
        # TODO(Adriant): Handle expire status properly.

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
            notes = {}
            for action in actions:
                notes[action.__unicode__()] = [action.submit(data), ]
            token.registration.completed = True
            token.registration.save()
            token.delete()

            return Response({'notes': notes}, status=200)
        except KeyError:
            pass


class ActionView(APIView):
    """Base class for api calls that start a Registration.
       Until it is moved to settings, 'default_action' is a
       required hardcoded field."""

    def get(self, request):
        actions = [self.default_action, ]

        actions += settings.API_ACTIONS.get(self.__class__.__name__, [])

        required_fields = set()

        for action in actions:
            act_tuple = settings.ACTION_CLASSES[action]
            for field in act_tuple[0].required:
                required_fields.add(field)

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
            act_tuple = settings.ACTION_CLASSES[action]

            serializer = act_tuple[1](data=request.data)

            act_list.append({
                'name': action,
                'action': act_tuple[0],
                'serializer': serializer})

            if not serializer.is_valid():
                valid = False

        if valid:
            ip_addr = request.META['REMOTE_ADDR']
            keystone_user = request.keystone_user

            registration = Registration.objects.create(
                reg_ip=ip_addr, keystone_user=json.dumps(keystone_user))
            registration.save()

            notes = {}
            i = 1
            for act in act_list:
                action = act['action'](
                    data=act['serializer'].data, registration=registration,
                    order=i
                )
                i += 1

                notes[act['name']] = []
                notes[act['name']] += action.pre_approve()

            registration.notes = json.dumps(notes)
            registration.save()
            return {'registration': registration,
                    'notes': notes}
        else:
            errors = {}
            for act in act_list:
                errors.update(act['serializer'].errors)
            return {'errors': errors}

    def approve(self, registration):
        registration.approved = True

        action_models = registration.actions
        actions = []

        valid = True
        for action in action_models:
            act = action.get_action()
            actions.append(act)

            if not act.valid:
                valid = False

        if valid:
            notes = json.loads(registration.notes)

            for action in actions:
                notes[action.__unicode__()] += action.post_approve()

                if not action.valid:
                    valid = False

            registration.notes = json.dumps(notes)
            registration.save()

            # TODO(Adriant): Need to check if token is required.
            # if not, just submit if valid.
            if valid:
                create_token(registration)
                return Response({'notes': ['created token']}, status=200)
        return Response({'notes': ['action invalid']}, status=400)


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

    # Need decorators?:
    # @admin_or_owner
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
