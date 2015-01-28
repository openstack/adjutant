class KeystoneHeaderUnwrapper(object):
    """"""
    def process_request(self, request):
        try:
            token_data = {
                'project_name': request.META['HTTP_X_PROJECT_NAME'],
                'project_id': request.META['HTTP_X_PROJECT_ID'],
                'roles': request.META['HTTP_X_ROLES'].split(','),
                'username': request.META['HTTP_X_USER_NAME'],
                'user_id': request.META['HTTP_X_USER_ID'],
                'authenticated': request.META['HTTP_X_IDENTITY_STATUS']
            }
        except KeyError:
            token_data = {}
        request.keystone_user = token_data
