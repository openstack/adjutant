from rest_framework import status
from rest_framework.test import APITestCase
from api_v1.models import Registration, Token


class WorkFlowTests(APITestCase):
    """Tests to ensure the approval/token workflow does
       what is expected. These test don't check final
       results for actions, simply that the registrations,
       action, and tokens are created/updated. """

    def test_new_user(self):
        """
        Ensure the new user workflow goes as expected.
        """
        url = "/api_v1/user"
        data = {'username': 'testuser', 'email': "test@example.com",
                'role': "Member", 'project_id': "test_project_id"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/api_v1/token/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_new_project(self):
        """
        Ensure the new project workflow goes as expected.
        """
        url = "/api_v1/project"
        data = {'project_name': "Test_Project", 'username': 'testuser',
                'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_registration = Registration.objects.all()[0]
        url = "/api_v1/registration/" + new_registration.uuid
        response = self.client.post(url, {'approved': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_token = Token.objects.all()[0]
        url = "/api_v1/token/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BaseModelTests(APITestCase):
    """"""

    def test_newuser_action(self):
        """
        """
