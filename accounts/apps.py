"""Django app configuration for the accounts package.

Registers the app under the label ``core`` (to avoid clashing with
Django's built-in ``accounts`` naming) and exposes a human-friendly
name in the admin.
"""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    label = 'core'
    verbose_name = 'Accounts'
