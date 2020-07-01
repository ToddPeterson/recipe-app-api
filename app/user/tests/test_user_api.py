from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status


CREATE_USER_URL = reverse('user:create')
TOKEN_URL = reverse('user:token')
ME_URL = reverse('user:me')


def create_user(**params):
    return get_user_model().objects.create_user(**params)


class PublicUserApiTests(TestCase):
    """Test the users API (public)"""

    def setUp(self):
        self.client = APIClient()

    def test_create_valid_user_success(self):
        """Test creating user with valid payload is successful"""
        payload = {
            'email': 'test@email.com',
            'password': 'testpass',
            'name': 'My Name'
        }
        req = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(req.status_code, status.HTTP_201_CREATED)

        user = get_user_model().objects.get(**req.data)
        self.assertTrue(user.check_password(payload['password']))
        self.assertNotIn('password', req.data)

    def test_user_exists(self):
        """Test creating a user that already exists fails"""
        payload = {
            'email': 'fake@email.com',
            'password': 'password123',
            'name': 'Real Name'
        }
        create_user(**payload)

        req = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(req.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_too_short(self):
        """Test that the password must be more than 5 characters"""
        payload = {
            'email': 'email@email.com',
            'password': 'pw',
            'name': 'Test Name'
        }
        req = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(req.status_code, status.HTTP_400_BAD_REQUEST)

        user_exists = get_user_model().objects.filter(
            email=payload['email']
        ).exists()
        self.assertFalse(user_exists)

    def test_create_token_for_user(self):
        """Test that a token is created for the user"""
        payload = {
            'email': 'test@email.com',
            'password': 'testpass'
        }
        create_user(**payload)
        req = self.client.post(TOKEN_URL, payload)

        self.assertIn('token', req.data)
        self.assertEqual(req.status_code, status.HTTP_200_OK)

    def test_create_token_invalid_credentials(self):
        """Test that token is not created if invalid credentials are given"""
        create_user(
            email="test@email.com",
            password="testpassword"
        )
        payload = {
            'email': 'test@email.com',
            'password': 'wrongpass'
        }
        req = self.client.post(TOKEN_URL, payload)

        self.assertNotIn('token', req.data)
        self.assertEqual(req.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_token_no_user(self):
        """Test that token is not created if user doesn't exist"""
        payload = {
            'email': 'fake@email.com',
            'password': 'letmein'
        }
        req = self.client.post(TOKEN_URL, payload)

        self.assertNotIn('token', req.data)
        self.assertEqual(req.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_token_missing_field(self):
        """Test that email and password are required"""
        create_user(
            email='user@email.com',
            password='userpassword'
        )
        req = self.client.post(
            TOKEN_URL,
            {'email': 'user@email.com', 'password': ''}
        )

        self.assertNotIn('token', req.data)
        self.assertEqual(req.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_user_unauthrorized(self):
        """Test that authentication is required for users"""
        req = self.client.get(ME_URL)

        self.assertEqual(req.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateUserApiTests(TestCase):
    """Test API requests that require authentication"""

    def setUp(self):
        self.user = create_user(
            email='authuser@email.com',
            password='secure_pass',
            name='User Name'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_profile_success(self):
        """Test retrieving profile for logged in user"""
        req = self.client.get(ME_URL)

        self.assertEqual(req.status_code, status.HTTP_200_OK)
        self.assertEqual(req.data, {
            'name': self.user.name,
            'email': self.user.email
        })

    def test_post_me_not_allowed(self):
        """Test that post is not allowed on the me url"""
        req = self.client.post(ME_URL, {})

        self.assertEqual(req.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_update_user_profile(self):
        """Test updating the user profile for authenticated user"""
        payload = {
            'name': 'New Name',
            'password': 'newpass123'
        }

        req = self.client.patch(ME_URL, payload)
        self.user.refresh_from_db()

        self.assertEqual(self.user.name, payload['name'])
        self.assertTrue(self.user.check_password(payload['password']))
        self.assertEqual(req.status_code, status.HTTP_200_OK)
