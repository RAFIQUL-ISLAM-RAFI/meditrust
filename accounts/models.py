from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager


class MediTrustUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('is_verified', True)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        MANUFACTURER = 'MANUFACTURER', 'Manufacturer'
        RETAILER = 'RETAILER', 'Retailer'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.RETAILER)
    license_no = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    organization_name = models.CharField(max_length=150, blank=True)
    is_verified = models.BooleanField(default=True)
    objects = MediTrustUserManager()

    def __str__(self):
        return self.organization_name or self.get_full_name() or self.username
