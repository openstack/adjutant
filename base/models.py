from django.db import models
import json
from django.utils import timezone
# from openstack_clients import get_keystoneclient
from serializers import NewUserSerializer, NewProjectSerializer


class Action(models.Model):
    """Database model representation of the related action."""
    action_name = models.CharField(max_length=200)
    action_data = models.TextField()
    state = models.CharField(max_length=200, default="default")
    valid = models.BooleanField(default=False)
    need_token = models.BooleanField(default=True)
    registration = models.ForeignKey('api_v1.Registration')

    created = models.DateTimeField(default=timezone.now)

    def get_action(self):
        """"""
        data = json.loads(self.action_data)
        return ACTION_CLASSES[self.action_name][0](data=data,
                                                   action_model=self)


class BaseAction(object):
    """Base class for the object wrapping around the database model.
       Setup to allow multiple action types and different internal logic
       per type but built from a single database type.
       - 'required' defines what fields to setup from the data.
       - 'token_fields' defined which fields are needed by this action
         at the token stage."""

    def __init__(self, data, action_model=None, registration=None):
        """Build itself around an existing database model,
           or build itself and creates a new database model.
           Sets up required data as fields."""

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
    """Setup a new user with a role on the given project.
       Creates the user if they don't exist, otherwise
       if the username and email for the request match the
       existing one, will simply add the project role."""

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
        # TODO(Adriant): Figure out how to best propagate the request
        # data to here, or if the above validation needs to happen elsewhere.

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
    """Similar functionality as the NewUser action,
       but will create the project if valid. Will setup
       the user (existing or new) with the 'default_role'."""
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
    """Simple action to reset a password for a given user."""

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


# this needs to be moved to settings... somehow, or some better plugin
# functionality needs to be setup. Maybe all app model functions attach their
# 'ACTION_CLASSES' to a global one in settings on import.
ACTION_CLASSES = {
    'NewUser': (NewUser, NewUserSerializer),
    'NewProject': (NewProject, NewProjectSerializer)
}
