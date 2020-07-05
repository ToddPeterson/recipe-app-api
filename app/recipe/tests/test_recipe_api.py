import os
import tempfile

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Tag, Ingredient

from recipe.serializers import RecipeSerializer, RecipeDetailSerializer


RECIPE_URL = reverse('recipe:recipe-list')


def image_upload_url(recipe_id):
    """Return url for recipe image upload"""
    return reverse('recipe:recipe-upload-image', args=[recipe_id])


def detail_url(recipe_id):
    """return recipe detail URL"""
    return reverse('recipe:recipe-detail', args=[recipe_id])


def sample_tag(user, name='Main course'):
    """Create and return a sample tag"""
    return Tag.objects.create(user=user, name=name)


def sample_ingredient(user, name='Thyme'):
    """Create and return a sample ingredient"""
    return Ingredient.objects.create(user=user, name=name)


def sample_recipe(user, **params):
    """Create and return a sample recipe"""
    defaults = {
        'title': 'Sample recipe',
        'time_minutes': 10,
        'price': 5.00
    }
    defaults.update(params)

    return Recipe.objects.create(user=user, **defaults)


class PublicRecipeApiTests(TestCase):
    """Test unauthenticataed recipe api access"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test that authentication is required"""
        req = self.client.get(RECIPE_URL)

        self.assertEqual(req.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeApiTests(TestCase):
    """Test authenticated recipe API access"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'test@email.com',
            'testpass'
        )
        self.client.force_authenticate(self.user)

    def test_retrieve_recipes(self):
        """Test retrieving a list of recipes"""
        sample_recipe(user=self.user)
        sample_recipe(user=self.user)

        req = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(req.status_code, status.HTTP_200_OK)
        self.assertEqual(req.data, serializer.data)

    def test_recipe_limited_to_user(self):
        """Test retrieving recipes limited to user's recipes"""
        other_user = get_user_model().objects.create_user(
            'other@email.com',
            'password123'
        )
        sample_recipe(user=other_user)
        sample_recipe(user=self.user)

        req = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(req.status_code, status.HTTP_200_OK)
        self.assertEqual(len(req.data), 1)
        self.assertEqual(req.data, serializer.data)

    def test_view_recipe_detail(self):
        """Test viewing a recipe detail"""
        recipe = sample_recipe(user=self.user)
        recipe.tags.add(sample_tag(user=self.user))
        recipe.ingredients.add(sample_ingredient(user=self.user))

        url = detail_url(recipe.id)
        req = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(req.data, serializer.data)

    def test_create_basic_recipe(self):
        """Test creating recipe"""
        payload = {
            'title': 'Cheesecake',
            'time_minutes': 30,
            'price': 5.00
        }
        req = self.client.post(RECIPE_URL, payload)

        self.assertEqual(req.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.get(id=req.data['id'])
        for key in payload:
            self.assertEqual(payload[key], getattr(recipe, key))

    def test_create_recipe_with_tags(self):
        """Test creating recipe with tags"""
        tag1 = sample_tag(user=self.user, name='Gluten free')
        tag2 = sample_tag(user=self.user, name='Breakfast')
        payload = {
            'title': 'Banana Pancakes',
            'tags': [tag1.id, tag2.id],
            'time_minutes': 15,
            'price': 3.00
        }
        req = self.client.post(RECIPE_URL, payload)

        self.assertEqual(req.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.get(id=req.data['id'])
        tags = recipe.tags.all()
        self.assertEqual(tags.count(), 2)
        self.assertIn(tag1, tags)
        self.assertIn(tag2, tags)

    def test_create_recipe_with_ingredients(self):
        """Test creating a recipe with ingredients"""
        ing1 = sample_ingredient(user=self.user, name='flour')
        ing2 = sample_ingredient(user=self.user, name='water')
        payload = {
            'title': 'Pizza dough',
            'ingredients': [ing1.id, ing2.id],
            'time_minutes': 480,
            'price': 2.50
        }
        req = self.client.post(RECIPE_URL, payload)

        self.assertEqual(req.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.get(id=req.data['id'])
        ingredients = recipe.ingredients.all()
        self.assertEqual(ingredients.count(), 2)
        self.assertIn(ing1, ingredients)
        self.assertIn(ing2, ingredients)

    def test_partial_update_recipe(self):
        """Test updating a recipe with patch"""
        recipe = sample_recipe(user=self.user)
        recipe.tags.add(sample_tag(user=self.user))
        new_tag = sample_tag(user=self.user, name='Soup')

        payload = {
            'title': 'Italian Wedding Soup',
            'tags': [new_tag.id]
        }
        url = detail_url(recipe.id)
        self.client.patch(url, payload)

        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload['title'])

        tags = recipe.tags.all()
        self.assertEqual(len(tags), 1)
        self.assertIn(new_tag, tags)

    def test_full_update_recipe(self):
        """Test updating a recipe with put"""
        recipe = sample_recipe(user=self.user)
        recipe.tags.add(sample_tag(user=self.user))
        payload = {
            'title': 'Penne Arrabiata',
            'time_minutes': 26,
            'price': 5.00
        }
        url = detail_url(recipe.id)
        self.client.put(url, payload)

        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.time_minutes, payload['time_minutes'])
        self.assertEqual(recipe.price, payload['price'])

        tags = recipe.tags.all()
        self.assertEqual(len(tags), 0)

    def test_filter_recipes_by_tag(self):
        """Test returning recipes with specific tags"""
        recipe1 = sample_recipe(user=self.user, title='Curry')
        recipe2 = sample_recipe(user=self.user, title='Shwarma')
        tag1 = sample_tag(user=self.user, name='Vegan')
        tag2 = sample_tag(user=self.user, name='Vegetarian')
        recipe1.tags.add(tag1)
        recipe2.tags.add(tag2)
        recipe3 = sample_recipe(user=self.user, title='steak')

        req = self.client.get(
            RECIPE_URL,
            {'tags': f'{tag1.id},{tag2.id}'}
        )

        serializer1 = RecipeSerializer(recipe1)
        serializer2 = RecipeSerializer(recipe2)
        serializer3 = RecipeSerializer(recipe3)

        self.assertIn(serializer1.data, req.data)
        self.assertIn(serializer2.data, req.data)
        self.assertNotIn(serializer3.data, req.data)

    def test_filter_recipes_by_ingredients(self):
        """Test returning ingredients with specific ingredients"""
        recipe1 = sample_recipe(user=self.user, title='Curry')
        recipe2 = sample_recipe(user=self.user, title='Shwarma')
        ing1 = sample_ingredient(user=self.user, name='Coconut milk')
        ing2 = sample_ingredient(user=self.user, name='Paneer')
        recipe1.ingredients.add(ing1)
        recipe2.ingredients.add(ing2)
        recipe3 = sample_recipe(user=self.user, title='Steak')

        req = self.client.get(
            RECIPE_URL,
            {'ingredients': f'{ing1.id},{ing2.id}'}
        )

        serializer1 = RecipeSerializer(recipe1)
        serializer2 = RecipeSerializer(recipe2)
        serializer3 = RecipeSerializer(recipe3)

        self.assertIn(serializer1.data, req.data)
        self.assertIn(serializer2.data, req.data)
        self.assertNotIn(serializer3.data, req.data)


class RecipeImageUploadTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'user@email.com',
            'testpass'
        )
        self.client.force_authenticate(self.user)
        self.recipe = sample_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image_to_recipe(self):
        """Test uploading an image to recipe"""
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix='.jpg') as ntf:
            img = Image.new('RGB', (10, 10))
            img.save(ntf, format='JPEG')
            ntf.seek(0)
            req = self.client.post(url, {'image': ntf}, format='multipart')

        self.recipe.refresh_from_db()
        self.assertEqual(req.status_code, status.HTTP_200_OK)
        self.assertIn('image', req.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading an invalid image"""
        url = image_upload_url(self.recipe.id)
        req = self.client.post(url, {'image': 'nothing'}, format='multipart')

        self.assertEqual(req.status_code, status.HTTP_400_BAD_REQUEST)
