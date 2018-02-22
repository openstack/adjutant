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

Each action class has the functions "pre_approve", "post_approve", and
"submit". These relate to stages of the approval process, and any python code
can be executed in those functions, some of which should ideally be validation.

Multiple actions can be chained together under one Task and will execute in
the defined order. Actions can pass information along via an in memory
cache/field on the task object, but that is only safe for the same stage of
execution. Actions can also store data back to the database if their logic
requires some info passed along to a later step of execution.

See ``actions.models`` and ``actions.v1`` for a good idea of Actions.

Tasks originate at a TaskView, and start the action processing. They encompass
the user side of interaction.

The main workflow consists of three possible steps which can be executed at
different points in time, depending on how the TaskView and the actions within
it are defined.

The base use case is three stages:

* Recieve Request
    * Validate request data against action serializers.
    * If valid, setup Task to represent the request, and the Actions specified
      for that TaskView.
    * The service runs the pre_approve function on all actions which should do
      any self validation to mark the actions themselves as valid or invalid,
      and populating the nodes in the Task based on that.
* Admin Approval
    * An admin looks at the Task and its notes.
    * If they decide it is safe to approve, they do so.
        * If there are any invalid actions approval will do nothing until the
          action data is updated and initial validation is rerun.
    * The service runs the post_approve function on all actions.
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

There are cases and TaskViews that auto-approve, and thus automatically do the
middle step right after the first. There are also others which do not need a
Token and thus run the submit step as part of the second, or even all three at
once. The exact number of 'steps' and the time between them depends on the
definition of the TaskView.

Actions themselves can also effectively do anything within the scope of those
three stages, and there is even the ability to chain multiple actions together,
and pass data along to other actions.

Details for adding taskviews and actions can be found on the :doc:`plugins`
page.


What is an Action?
====================

Actions are a generic database model which knows what 'type' of action it is.
On pulling the actions related to a Task from the database we wrap it into the
appropriate class type which handles all the logic associated with that action
type.

An Action is both a simple database representation of itself, and a more
complex in memory class that handles all the logic around it.

Each action class has the functions "pre_approve", "post_approve", and
"submit". These relate to stages of the approval process, and any python code
can be executed in those functions.

What is a Task?
================
A task is a top level model representation of the request. It wraps the
request metadata, and based on the TaskView, will have actions associated with
it.


What is a Token?
==================

A token is a unique identifier linking to a task, so that anyone submitting
the token will submit to the actions related to the task.

What is an TaskView?
====================

TaskViews are classes which extend the base TaskView class and use its inbuilt
functions to process actions. They also have actions associated with them and
the inbuilt functions from the base class are there to process and validate
those against data coming in.

The TaskView will process incoming data and build it into a Task,
and the related Action classes.

The base TaskView class has three functions:

* get
    * just a basic view function that by default returns list of actions,
      and their required fields for the action view.
* process_actions
    * needs to be called in the TaskView definition
    * A function to run the processing and validation of request data for
      actions.
    * Builds and returns the task object, or the validation errors.

At their base TaskViews are django-rest ApiViews, with a few magic functions
to wrap the task logic.
