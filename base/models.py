from django.db import models
import json
from django.utils import timezone
# from openstack_clients import get_keystoneclient
from serializers import NewUserSerializer, NewProjectSerializer


class Action(models.Model):

    action_name = models.CharField(max_length=200)
    action_data = models.TextField()
    state = models.CharField(max_length=200, default="default")
    valid = models.BooleanField(default=False)
    need_token = models.BooleanField(default=True)
    registration = models.ForeignKey('api_v1.Registration')

    created = models.DateTimeField(default=timezone.now)

    def get_action(self):
        data = json.loads(self.action_data)
        return ACTION_CLASSES[self.action_name][0](data=data,
                                                            action_model=self)


class BaseAction(object):

    def __init__(self, data, action_model=None, registration=None):
        # constructor builds a NEW object to DB,
        # or loads one from an action

        for field in self.required:
            field_data = data[field]
            setattr(self, field, field_data)

        if action_model:
            self.action = action_model
        else:
            # make new model and save in db
            action = Action.objects.create(
                action_name=self.__class__.__name__,
                action_data=json.dumps(data),
                registration=registration
            )
            action.save()
            self.action = action

    @property
    def valid(self):
        return self.action.valid

    def pre_approve(self):
        return self._pre_approve()

    def post_approve(self):
        return self._post_approve()

    def submit(self, token_data):
        return self._submit(token_data)

    def _pre_approve(self):
        raise NotImplementedError

    def _post_approve(self):
        raise NotImplementedError

    def _submit(self, token_data):
        raise NotImplementedError

    def __unicode__(self):
        return self.__class__.__name__


class NewUser(BaseAction):
    """"""

    required = [
        'username',
        'email',
        'project_id',
        'role'
    ]

    token_fields = ['password']

    def _validate(self):
        # keystone = get_keystoneclient()

        # user = keystone.users.get(self.username)
        user = None

        # TODO(Adriant): Ensure that the project_id given is for a
        # real project, and that it matches the project in the token
        # if the token isn't an admin one.

        if user:
            if user.email == self.email:
                self.action.valid = True
                self.action.need_token = True
                self.action.state = "existing"
                self.action.save()
                return ['Existing user with matching email.']
            else:
                return ['Existing user with non-matching email.']
        else:
            self.action.valid = True
            self.action.save()
            return ['No user present with existing username']

    def _pre_approve(self):
        return self._validate()
        

    def _post_approve(self):
        return self._validate()

    def _submit(self, token_data):
        self._validate()

        if self.valid:
            if self.action.state == "default":
                return [('User %s has been created, and given role %s in project %s.'
                         % (self.username, self.role, self.project_id)), ]
            elif self.action.state == "existing":
                return [('Existing user %s has been given role %s in project %s.'
                         % (self.username, self.role, self.project_id)), ]


class NewProject(BaseAction):
    """"""
    required = [
        'project_name',
        'username',
        'email'
    ]

    default_role = "project_owner"

    token_fields = ['password']

    def _validate(self):
        # keystone = get_keystoneclient()

        # user = keystone.users.get(self.username)
        # project = keystone.users.get(self.username)
        user = None
        project = None

        notes = []

        if user:
            if user.email == self.email:
                self.action.valid = True
                self.action.need_token = True
                self.action.state = "attach"
                self.action.save()
                notes.append("Existing user '%s' with matching email." %
                             self.email)
            else:
                notes.append("Existing user '%s' with non-matching email." %
                             self.username)
        else:
            self.action.valid = True
            self.action.save()
            notes.append("No user present with existing username '%s'." %
                         self.username)

        if project:
            notes.append("Existing project with name '%s'." % self.project_name)
        else:
            notes.append("No existing project with name '%s'." % self.project_name)
        return notes

    def _pre_approve(self):
        return self._validate()   

    def _post_approve(self):
        return self._validate()

    def _submit(self, token_data):
        self._validate()

        if self.valid:
            if self.action.state == "default":
                return [('User %s has been created, and given role %s in project %s.'
                         % (self.username, self.default_role, self.project_name)), ]
            elif self.action.state == "existing":
                return [('Existing user %s has been given role %s in project %s.'
                         % (self.username, self.default_role, self.project_name)), ]


class ResetUser(BaseAction):
    """"""

    # The validity of these fields need to be checked
    # via the api, so that simple stuff like
    # "is this a valid username format"
    # and other checks we can send back to the user safely
    username = models.CharField(max_length=200)
    email = models.EmailField()

    required = [
        'username',
        'email'
    ]

    token_fields = ['password']

    def _pre_approve(self):
        msg = "Not implemented yet."

        return msg

    def _post_approve(self):
        msg = "Not implemented yet."

        return msg

    def _submit(self, token_data):
        msg = "Not implemented yet."

        return msg


ACTION_CLASSES = {
    'NewUser': (NewUser, NewUserSerializer),
    'NewProject': (NewProject, NewProjectSerializer)
}
