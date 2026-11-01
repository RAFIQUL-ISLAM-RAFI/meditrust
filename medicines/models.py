import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


def new_code():
    return uuid.uuid4().hex


class Medicine(models.Model):
    name = models.CharField(max_length=100)
    generic_name = models.CharField(max_length=100)
    manufacturer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='medicines')
    composition = models.TextField(blank=True)
    description = models.TextField(blank=True)
    side_effects = models.TextField(blank=True)
    precautions = models.TextField(blank=True)
    dosage_info = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.generic_name})"

    class Meta:
        db_table = 'core_medicine'


class Batch(models.Model):
    batch_number = models.CharField(max_length=50)
    expiry_date = models.DateField()
    batch_code = models.CharField(max_length=32, unique=True, default=new_code)
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='batches')
    created_at = models.DateTimeField(auto_now_add=True)
    manufacture_date = models.DateField(null=True, blank=True)
    is_recalled = models.BooleanField(default=False)
    recall_reason = models.TextField(blank=True)
    recalled_at = models.DateTimeField(null=True, blank=True)
    recalled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='recalled_batches')
    integrity_signature = models.CharField(max_length=64, blank=True)

    @property
    def is_expired(self):
        return self.expiry_date < timezone.localdate()

    def save(self, *args, **kwargs):
        if not self.integrity_signature:
            from .utils import batch_signature
            self.integrity_signature = batch_signature(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicine.name} - {self.batch_number}"

    class Meta:
        db_table = 'core_batch'


class MedicineUnit(models.Model):
    unique_hash_code = models.CharField(max_length=64, unique=True)
    serial_number = models.CharField(max_length=20, unique=True)
    total_pills = models.PositiveIntegerField(default=10)
    sold_pills = models.PositiveIntegerField(default=0)
    current_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_units')
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='units')
    integrity_signature = models.CharField(max_length=64, blank=True)
    first_public_visitor = models.CharField(max_length=64, blank=True)
    first_public_check = models.DateTimeField(null=True, blank=True)
    duplicate_detected = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.integrity_signature:
            from .utils import unit_signature
            self.integrity_signature = unit_signature(self)
        super().save(*args, **kwargs)

    @property
    def remaining(self):
        return self.total_pills - self.sold_pills

    def __str__(self):
        return self.serial_number

    class Meta:
        db_table = 'core_medicineunit'
