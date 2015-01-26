from django.db import models
import json


class Registration(models.Model):
    """"""
    # who is this:
    reg_ip = models.GenericIPAddressField()

    # what do we know about them:
    notes = models.TextField(default="{}")

    approved = models.BooleanField(default=False)

    completed = models.BooleanField(default=False)

    @property
    def actions(self):
        return self.action_set.all()

    def as_dict(self):
        actions = []
        for action in self.actions:
            actions.append({
                "action_name": action.action_name,
                "data": json.loads(action.action_data),
                "valid": action.valid
            })

        return {
            "ip_address": self.reg_ip, "notes": json.loads(self.notes),
            "approved": self.approved, "completed": self.completed,
            "actions": actions, "id": self.id
        }


class Token(models.Model):
    """"""

    registration = models.ForeignKey(Registration)
    token = models.TextField(primary_key=True)
    expires = models.DateTimeField()
