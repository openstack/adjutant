from copy import deepcopy


def dict_merge(a, b):
    """
    Recursively merges two dicts.
    If both a and b have a key who's value is a dict then dict_merge is called
    on both values and the result stored in the returned dictionary.
    """
    if not isinstance(b, dict):
        return b
    result = deepcopy(a)
    for k, v in b.iteritems():
        if k in result and isinstance(result[k], dict):
                result[k] = dict_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


def setup_task_settings(default, task_settings):
    """
    Cascading merge of the default settings, and the
    settings for each task_type.
    """
    new_task_settings = {}

    for task, settings in task_settings.iteritems():
        new_task_settings[task] = dict_merge(default, settings)

    return new_task_settings
