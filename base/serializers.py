from rest_framework import serializers


class NewUserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    project_id = serializers.CharField(max_length=200)

    role_options = (('project_mod', 'Project Owner (can add new users)'),
                    ('Member', "Project Member (can't add new users)"))
    role = serializers.ChoiceField(choices=role_options)


class NewProjectSerializer(serializers.Serializer):
    project_name = serializers.CharField(max_length=200)
    username = serializers.CharField(max_length=200)
    email = serializers.EmailField()
