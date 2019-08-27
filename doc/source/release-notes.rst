==========================
Working with Release Notes
==========================

The Adjutant team uses `reno
<https://docs.openstack.org/reno/latest/user/usage.html>`_ to generate release
notes. These are important user-facing documents that must be included when a
user or operator facing change is performed, like a bug-fix or a new feature. A
release note should be included in the same patch the work is being performed.
Release notes should be short, easy to read, and easy to maintain. They also
`must` link back to any appropriate documentation if it exists. The following
conventions help ensure all release notes achieve those goals.

Most release notes either describe bug fixes or announce support for new
features, both of which are tracked using Launchpad. The conventions below rely
on links in Launchpad to provide readers with more context.

.. warning::

    We highly recommend taking careful thought when writing and reviewing
    release notes. Once a release note has been published with a formal
    release, updating it across releases will cause it to be published in a
    subsequent release. Reviews that update, or modify, a release note from a
    previous release outside of the branch it was added in should be rejected
    unless it's required for a very specific case.

    Please refer to reno's `documentation
    <https://docs.openstack.org/reno/latest/user/usage.html>`_ for more
    information.

Release Notes for Bugs
======================

When creating a release note that communicates a bug fix, use the story number
in the name of the release note:

.. code-block:: bash

    $ tox -e venv reno new story-1652012
    Created new notes file in releasenotes/notes/story-1652012-7c53b9702b10084d.yaml

The body of the release note should clearly explain how the impact will affect
users and operators. It should also include why the change was necessary but
not be overspecific about implementation details, as that can be found in the
commit and the bug report. It should contain a properly formatted link in
reStructuredText that points back to the original bug report used to track the
fix. This ensures the release note is kept short and to-the-point while
providing readers with additional resources:

.. code-block:: yaml

    ---
    fixes:
      - |
        [`bug 1652012 <https://storyboard.openstack.org/#!/story/111111>`_]
        This bug was fixed because X and we needed to maintain a certain level
        of backwards compatibility with the fix despite so it still defaults to
        an unsafe value.
    deprecations:
      - >
        X is now deprecated and should no longer be used. Instead use Y.


Release Notes for Features
==========================

Release notes detailing feature work follow the same basic format, since
features are also tracked as stories.

.. code-block:: bash

    $ tox -e venv reno new story-1652012
    Created new notes file in releasenotes/notes/story-1652012-7c53b9702b10084d.yaml

Just like release notes communicating bug fixes, release notes detailing
feature work must contain a link back to the story. Readers should be able
to easily discover all patches that implement the feature, as well as find
links to the full specification and documentation. The release notes can be
added to the last patch of the feature. All of this is typically found in the
story on storyboard:

.. code-block:: yaml

    ---
    features:
      - >
        [`story 1652012 <https://storyboard.openstack.org/#!/story/222222>`_]
        We now support Q
    upgrade:
      - >
        We highly recommend people using W to switch to using Q

In the rare case there is a release note that does not pertain to a bug or
feature work, use a sensible slug and include any documentation relating to the
note. We can iterate on the content and application of the release note during
the review process.

For more information on how and when to create release notes, see the
`project-team-guide
<https://docs.openstack.org/project-team-guide/release-management.html#how-to-add-new-release-notes>`_.
