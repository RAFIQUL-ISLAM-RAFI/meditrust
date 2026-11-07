"""Structural sanity tests for the MediTrust project.

Verifies that the three custom apps (accounts, medicines, tracking) are
registered, collectively own seven models, and declare eleven foreign
keys — matching the project specification.
"""
from django.apps import apps
from django.db import models
from django.test import SimpleTestCase


class ProjectStructureTests(SimpleTestCase):
    def test_three_registered_custom_apps_own_seven_models_and_eleven_foreign_keys(self):
        custom = [app for app in apps.get_app_configs() if not app.name.startswith('django.')]
        self.assertEqual({app.name for app in custom}, {'accounts', 'medicines', 'tracking'})
        self.assertEqual({app.name: len(list(app.get_models())) for app in custom},
                         {'accounts': 1, 'medicines': 3, 'tracking': 3})
        project_models = [model for app in custom for model in app.get_models()]
        self.assertEqual(len(project_models), 7)
        self.assertEqual(sum(isinstance(field, models.ForeignKey)
                             for model in project_models for field in model._meta.fields), 11)

