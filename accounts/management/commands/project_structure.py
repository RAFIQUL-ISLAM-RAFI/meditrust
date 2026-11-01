from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models


class Command(BaseCommand):
    help = 'Report the registered custom apps, their models and explicit foreign keys.'

    def handle(self, *args, **options):
        configs = [app for app in apps.get_app_configs() if not app.name.startswith('django.')]
        model_total = key_total = 0
        for config in configs:
            self.stdout.write(config.name + ':')
            for model in config.get_models():
                keys = [field.name for field in model._meta.fields if isinstance(field, models.ForeignKey)]
                model_total += 1
                key_total += len(keys)
                self.stdout.write(f"  {model.__name__}: {len(keys)} foreign keys" + (f" ({', '.join(keys)})" if keys else ''))
        self.stdout.write(self.style.SUCCESS(f'Total: {len(configs)} custom apps, {model_total} model classes, {key_total} foreign key fields.'))
