# from django.shortcuts import render
# from base.models import User, Tenant
# from models import Registration
from rest_framework.views import APIView
from rest_framework.response import Response
from models import Registration, Token
import json
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4
from base.models import ACTION_CLASSES

from django.conf import settings


def create_token(registration):
    # needs to be made configurable.
    expire = timezone.now() + timedelta(hours=24)
    uuid = uuid4().hex
    token = Token.objects.create(
        registration=registration,
        token=uuid,
        expires=expire
    )
    token.save()


class RegistrationList(APIView):

    def get(self, request, format=None):
        registrations = Registration.objects.all()
        reg_list = []
        for registration in registrations:
            reg_list.append(registration.as_dict())
        return Response(reg_list)


class RegistrationDetail(APIView):

    def get(self, request, uuid, format=None):
        print uuid
        registration = Registration.objects.get(uuid=uuid)
        return Response(registration.as_dict())

    def patch(self, request, id, format=None):
        pass

    def delete(self, request, id, format=None):
        pass


class RegistrationApprove(APIView):

    def post(self, request, uuid, format=None):
        registration = Registration.objects.get(uuid=uuid)
        registration.approved = True

        need_token = False
        valid = True
        notes = json.loads(registration.notes)

        actions = []

        for action in registration.actions:
            action_model = action.get_action()
            actions.append(action_model)
            notes[action_model.__unicode__()] += action_model.post_approve()

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
                    notes[action.__unicode__()] += [action.submit(data),]

                registration.notes = json.dumps(notes)
                registration.completed = True
                registration.save()

            return Response({'notes': notes}, status=200)


class TokenList(APIView):

    def get(self, request, format=None):
        return Response({'stuff': 'things'})

    def post(self, request, format=None):
        """"""


class TokenDetail(APIView):

    def get(self, request, id, format=None):
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
        token = Token.objects.get(token=id)

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
                notes[action.__unicode__()] = [action.submit(data),]
            token.registration.completed = True
            token.registration.save()
            token.delete()

            return Response({'notes': notes}, status=200)
        except KeyError:
            pass


class ActionView(APIView):

    def process_actions(self, request):

        actions = [self.default_action,]

        actions += settings.API_ACTIONS.get(self.__class__.__name__, [])

        act_dict = {}

        valid = True
        for action in actions:
            act_tuple = ACTION_CLASSES[action]

            serializer = act_tuple[1](data=request.data)

            act_dict[action] = {'action': act_tuple[0],
                                'serializer': serializer}

            if not serializer.is_valid():
                valid = False

        if valid:
            ip_addr = request.META['REMOTE_ADDR']

            registration = Registration.objects.create(reg_ip=ip_addr)
            registration.save()

            notes = {}
            for name, value in act_dict.iteritems():
                action = value['action'](
                    data=value['serializer'].data, registration=registration)

                notes[name] = []
                notes[name] += action.pre_approve()

            registration.notes = json.dumps(notes)
            registration.save()
            return {'registration': registration,
                    'notes': notes}
        else:
            errors = {}
            for value in act_dict.values():
                errors.update(value['serializer'].errors)
            return {'errors': errors}


class CreateProject(ActionView):

    default_action = "NewProject"

    def post(self, request, format=None):
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            return Response(errors, status=400)

        return Response({'notes': ['registration created']}, status=200)


class AttachUser(ActionView):

    default_action = 'NewUser'

    # Need decorators?:
    # @admin_or_owner
    def post(self, request, format=None):

        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            return Response(errors, status=400)


        registration = processed['registration']

        # auto approved if this endpoint is used
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

            if valid:
                create_token(registration)
                return Response({'notes': ['created token']}, status=200)


class ResetPassword(ActionView):

    def post(self, request, format=None):
        pass
