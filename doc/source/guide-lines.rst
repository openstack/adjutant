Project Guide Lines
===================

Because of the extremely vague scope of the Adjutant project, we need to have
some sensible guides lines to help us define what isn't part of it, and what
should or could be.

Adjutant is a service to let cloud providers build workflow around certain
actions, or to build smaller APIs around existing things in OpenStack. Or even
APIs to integrate with OpenStack, but do actions in external systems.

Ultimately Adjutant is a Django project with a few limitations, and the feature
set system probably exposes too much extra functionality which can be added.
Some of this we plan to cut down, and throw in some explicitly defined
limitations, but even with the planned limitations the framework will always
be very flexible.


Should a feature become part of core
++++++++++++++++++++++++++++++++++++

Core Adjutant is mostly two parts. The first is the underlying workflow system,
the APIs associated that, and the notifications. The second is the provider
configurable APIs. This separation will increase further as we try and distance
the workflow layer away from having one task linked to a view.

Anything that is a useful improvement to the task workflow framework and the
associated APIs and notifications system, is always useful for core. As part of
this we do include, and plan to keep adding to, a collection of generally
useful actions and tasks. For those we need to be clear what should be part of
core.

1. Is the action one that better makes sense as a feature in one of the
   existing services in OpenStack? If so, we should add it there, and then
   build an action in Adjutant that calls this new API or feature.
2. Is the action you want to add one that is useful or potentially useful to
   any cloud provider? If it is too specific, it should not be added to core.
3. Is the action you want to add talking to system outside of Adjutant itself
   or outside of OpenStack? If either, then it should not be added to core.
4. Is the task (a combination of actions), doing something that is already in
   some fashion in OpenStack, or better suited to be a feature in another
   OpenStack service. If so, it does not belong in core.

In addition to that, we include a collection of generally useful API views
which expose certain underlying tasks as part of the workflow framework. These
also need clarification as to when they should be in core. These are mostly a
way to build smaller APIs that cloud users can use consume that underneath are
using Adjutant's workflow framework. Or often build APIs that expose useful
wrappers or supplementary logic around existing OpenStack APIs and features.

1. Is the API you are building something that makes better sense as a feature
   in one of the other existing OpenStack services? If so, it doesn't belong in
   Adjutant core.
2. Does the API query systems outside of Adjutant or OpenStack? Or rely on
   actions or tasks that also need to consume systems outside of Adjutant or
   OpenStack.


.. note::

  If an action, task, or API doesn't fit in core, it may fit in a external feature
  set, potentially even one that is maintained by the core team. If a feature isn't
  yet present in OpenStack that we can build in Adjutant quickly, we can do so
  as a semi-official feature set with the knowledge that we plan to deprecate that
  feature when it becomes present in OpenStack proper. In addition this process
  allows us to potentially allow providers to expose a variant of the feature
  if they are running older versions of OpenStack that don't entirely support
  it, but Adjutant could via the feature set mechanism. This gives us a large amount
  of flexibility, while ensuring we aren't reinventing the wheel.


Appropriate locations for types of logic in Adjutant
++++++++++++++++++++++++++++++++++++++++++++++++++++

In Adjutant there are different elements of the system that are better suited
to certain types of logic either because of what they expose, or what level of
auditability is appropriate for a given area.

Actions and Tasks
*****************

Actions and Tasks (collections of actions), have no real constraint. An action
can do anything, and needs a high level of flexibility. Given that is the cases
they should ideally have sensible validation built in, and should log what
they'd done so it can be audited.

Pluggable APIs
**************

Within the pluggable APIs, there should never be any logic that changes
resources outside of Adjutant. They should either only change Adjutant internal
resources (such as cancel a task), or query and return data. Building an API
which can return a complex query across multiple OpenStack services is fine,
but if a resource in any of those services needs to be changed, that should
always be done by triggering an underlying task workflow. This keeps the logic
clean, and the changes auditable.

.. warning::

  Anyone writing feature sets that break the above convention will not be
  supported. We may help and encourage you to move to using the underlying
  workflows, but the core team won't help you troubleshoot any logic that isn't
  in the right place.
