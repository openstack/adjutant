###########
Development
###########

Adjutant is built around tasks and actions.

Actions are a generic database model which knows what 'type' of action it is.
On pulling the actions related to a Task from the database we wrap it into the
appropriate class type which handles all the logic associated with that action
type.

An Action is both a simple database representation of itself, and a more
complex in memory class that handles all the logic around it.

Each action class has the functions "prepare", "approve", and
"submit". These relate to stages of the approval process, and any python code
can be executed in those functions, some of which should ideally be validation.

Multiple actions can be chained together under one Task and will execute in
the defined order. Actions can pass information along via an in memory
cache/field on the task object, but that is only safe for the same stage of
execution. Actions can also store data back to the database if their logic
requires some info passed along to a later step of execution.

See ``actions.models`` and ``actions.v1`` for a good idea of Actions.

Tasks, like actions, are also a database representation, and a more complex in
memory class. These classes define what actions the task has, and certain other
elements of how it functions. Most of the logic for task and action processing
is in the base task class, with most interactions with tasks occuring via the
TaskManager.

See ``tasks.models`` and ``tasks.v1`` for a good idea of Tasks.

The main workflow consists of three possible steps which can be executed at
different points in time, depending on how the task and the actions within
it are defined.

The base use case is three stages:

* Receive Request
    * Validate request data against action serializers.
    * If valid, setup Task to represent the request, and the Actions specified
      for that Task.
    * The service runs the "prepare" function on all actions which should do
      any self validation to mark the actions themselves as valid or invalid,
      and populating the notes in the Task based on that.
* Auto or Admin Approval
    * Either a task is set to auto_approve or and admin looks at it to decide.
        * If they decide it is safe to approve, they do so.
            * If there are any invalid actions approval will do nothing until
              the action data is updated and initial validation is rerun.
    * The service runs the "approve" function on all actions.
    * If any of the actions require a Token to be issued and emailed for
      additional data such as a user password, then that will occur.
    * If no Token is required, the Task will run submit actions, and be
      marked as complete.
* Token Submit
    * User submits the Token data.
    * The service runs the submit function on all actions, passing along the
      Token data, normally a password.
    * The action will then complete with the given final data.
    * Task is marked as complete.

There are cases where Tasks auto-approve, and thus automatically do the
middle step right after the first. There are also others which do not need a
Token and thus run the submit step as part of the second, or even all three at
once. The exact number of 'steps' and the time between them depends on the
definition of the Task.

Actions themselves can also effectively do anything within the scope of those
three stages, and there is even the ability to chain multiple actions together,
and pass data along to other actions.

Details for adding task and actions can be found on the :doc:`feature-sets`
page.


What is an Action?
==================

Actions are a generic database model which knows what 'type' of action it is.
On pulling the actions related to a Task from the database we wrap it into the
appropriate class type which handles all the logic associated with that action
type.

An Action is both a simple database representation of itself, and a more
complex in memory class that handles all the logic around it.

Each action class has the functions "prepare", "approve", and
"submit". These relate to stages of the approval process, and any python code
can be executed in those functions.

What is a Task?
===============

A task is a top level model representation of the workflow. Much like an Action
it is a simple database representation of itself, and a more complex in memory
class that handles all the logic around it.

Tasks define what actions are part of a task, and handle the logic of
processing them.

What is a Token?
================

A token is a unique identifier linking to a task, so that anyone submitting
the token will submit to the actions related to the task.

What is a DelegateAPI?
======================

DelegateAPIs are classes which extend the base DelegateAPI class.

They are mostly used to expose underlying tasks as APIs, and they do so
by using the TaskManager to handle the workflow. The TaskManager will
handle the data validation, and raise error responses for errors that
the user should see. If valid the TaskManager will process incoming
data and build it into a Task, and the related Action classes.

DelegateAPIs can also be used for small arbitary queries, or building
a full suite of query and task APIs. They are built to be flexible, and
easily pluggable into Adjutant. At their base DelegateAPIs are Django
Rest Framework ApiViews, with a helpers for task handling.

The only constraint with DelegateAPIs is that they should not do any
resourse creation/alteration/deletion themselves. If you need to work with
resources, use the task layer and define a task and actions for it.
Building DelegateAPIs which just query other APIs and don't alter
resources, but need to return information about resources in other
systems is fine. These are useful small little APIs to suppliment any
admin logic you need to expose.
