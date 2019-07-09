import yaml

from django.core.management.base import BaseCommand

from confspirator import groups

from adjutant import config


def make_yaml_lines(val, depth, comment=False):
    new_lines = []
    line_prefix = "  " * (depth + 1)
    for line in yaml.dump(val).split('\n'):
        if line == '':
            continue
        if comment:
            new_lines.append(line_prefix + "# %s" % line)
        else:
            new_lines.append(line_prefix + line)
    return new_lines


def make_field_lines(field, depth):
    field_lines = []
    line_prefix = "  " * (depth + 1)
    field_type = field.type.__class__.__name__
    field_lines.append(line_prefix + "# %s" % field_type)
    field_help_text = "# %s" % field.help_text
    field_lines.append(line_prefix + field_help_text)

    default = ''
    if field.default is not None:
        default = field.default

    if not default and field.sample_default is not None:
        default = field.sample_default

    if field_type == "Dict":
        if default:
            field_lines.append(line_prefix + "%s:" % field.name)
            field_lines += make_yaml_lines(default, depth + 1)
        else:
            field_lines.append(line_prefix + "# %s:" % field.name)
    elif field_type == "List":
        if default:
            field_lines.append(line_prefix + "%s:" % field.name)
            field_lines += make_yaml_lines(default, depth + 1)
        else:
            field_lines.append(line_prefix + "# %s:" % field.name)
    else:
        if default == '':
            field_lines.append(line_prefix + "# %s: <your_value>" % field.name)
        else:
            default_str = " " + str(default)
            field_lines.append(line_prefix + "%s:%s" % (field.name, default_str))
    return field_lines


def make_group_lines(group, depth=0):
    group_lines = []
    line_prefix = "  " * depth
    group_lines.append(line_prefix + "%s:" % group.name)

    for child in group:
        if isinstance(child, groups.ConfigGroup):
            group_lines += make_group_lines(child, depth=depth + 1)
        else:
            group_lines += make_field_lines(child, depth)
    return group_lines


class Command(BaseCommand):
    help = ''

    def add_arguments(self, parser):
        parser.add_argument('--output-file', default="adjutant.yaml")

    def handle(self, *args, **options):
        print("Generating example file to: '%s'" % options['output_file'])

        base_lines = []
        for group in config._root_config:
            base_lines += make_group_lines(group)
            base_lines.append("")

        with open(options['output_file'], "w") as f:
            for line in base_lines:
                f.write(line)
                f.write("\n")
