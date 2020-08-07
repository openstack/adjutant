from django.core.management.base import BaseCommand

import confspirator

from adjutant import config


class Command(BaseCommand):
    help = "Produce an example config file for Adjutant."

    def add_arguments(self, parser):
        parser.add_argument("--output-file", default="adjutant.yaml")

    def handle(self, *args, **options):
        print("Generating example file to: '%s'" % options["output_file"])

        confspirator.create_example_config(config._root_config, options["output_file"])
