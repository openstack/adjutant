def management_command():
    """Entry-point for the 'stacktask' command-line admin utility."""
    import os
    import sys

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stacktask.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
