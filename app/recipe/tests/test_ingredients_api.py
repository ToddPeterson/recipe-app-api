from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Ingredient, Recipe

from recipe.serializers import IngredientSerializer


INGREDIENTS_URL = reverse('recipe:ingredient-list')


class PublicIngredientsApiTest(TestCase):
    """Test the publicly available ingredients api"""

    def setUp(self):
        self.client = APIClient()

    def test_login_required(self):
        """Test that login is required to access endpoint"""
        req = self.client.get(INGREDIENTS_URL)

        self.assertEqual(req.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredientsApiTest(TestCase):
    """Test the private ingredients API"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'test@email.com',
            'testpass'
        )
        self.client.force_authenticate(self.user)

    def test_retrieve_ingredient_list(self):
        """Test retrieving a list of ingredients"""
        Ingredient.objects.create(user=self.user, name='Worms')
        Ingredient.objects.create(user=self.user, name='Wine')

        req = self.client.get(INGREDIENTS_URL)

        ingredients = Ingredient.objects.all().order_by('-name')
        serializer = IngredientSerializer(ingredients, many=True)
        self.assertEqual(req.status_code, status.HTTP_200_OK)
        self.assertEqual(req.data, serializer.data)

    def test_ingredients_limited_to_user(self):
        """Test only ingredients for the authenticated user are returned"""
        other_user = get_user_model().objects.create_user(
            'other@email.com',
            'afdasdf'
        )
        Ingredient.objects.create(user=other_user, name='Water')
        ing = Ingredient.objects.create(user=self.user, name='Flour')

        req = self.client.get(INGREDIENTS_URL)

        self.assertEqual(req.status_code, status.HTTP_200_OK)
        self.assertEqual(len(req.data), 1)
        self.assertEqual(req.data[0]['name'], ing.name)

    def test_create_ingredient_successful(self):
        """Test creating a new ingredient"""
        payload = {
            'name': 'Squash'
        }
        self.client.post(INGREDIENTS_URL, payload)

        exists = Ingredient.objects.filter(
            user=self.user,
            name=payload['name']
        ).exists()

        self.assertTrue(exists)

    def test_create_ingredient_invalid(self):
        """Test creating invalid ingredient fails"""
        payload = {'name': ''}
        req = self.client.post(INGREDIENTS_URL, payload)

        self.assertEqual(req.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_ingredients_assigned_to_recipes(self):
        """Test filtering ingredients by assigned to recipe"""
        ing1 = Ingredient.objects.create(
            user=self.user,
            name='Pear'
        )
        ing2 = Ingredient.objects.create(
            user=self.user,
            name='Salami'
        )
        recipe = Recipe.objects.create(
            user=self.user,
            title='Sandwich',
            time_minutes=5,
            price=4.00
        )
        recipe.ingredients.add(ing2)

        req = self.client.get(INGREDIENTS_URL, {'assigned_only': 1})

        serializer1 = IngredientSerializer(ing1)
        serializer2 = IngredientSerializer(ing2)

        self.assertNotIn(serializer1.data, req.data)
        self.assertIn(serializer2.data, req.data)

    def test_retrieve_ingredients_assigned_unique(self):
        """Test filtering ingredients by assinged returns unique"""
        ing = Ingredient.objects.create(user=self.user, name='Bread')
        Ingredient.objects.create(user=self.user, name='Mustard')
        recipe1 = Recipe.objects.create(
            user=self.user,
            title='Toast',
            time_minutes=4,
            price=1.00
        )
        recipe2 = Recipe.objects.create(
            user=self.user,
            title='Raw Toast',
            time_minutes=4,
            price=1.00
        )
        recipe1.ingredients.add(ing)
        recipe2.ingredients.add(ing)

        req = self.client.get(INGREDIENTS_URL, {'assigned_only': 1})

        self.assertEqual(len(req.data), 1)
