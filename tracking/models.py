from django.conf import settings
from django.db import models


class OwnershipTransfer(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'

    unit = models.ForeignKey('medicines.MedicineUnit', on_delete=models.CASCADE, related_name='transfers')
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_transfers')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_transfers')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    transfer_date = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'core_ownershiptransfer'


class VerificationLog(models.Model):
    unit = models.ForeignKey('medicines.MedicineUnit', on_delete=models.CASCADE, related_name='logs', null=True, blank=True)
    scanned_at = models.DateTimeField(auto_now_add=True)
    location = models.CharField(max_length=100, blank=True)
    scan_count = models.PositiveIntegerField(default=1)
    is_suspicious = models.BooleanField(default=False)
    visitor_fingerprint = models.CharField(max_length=64, blank=True)
    verification_result = models.CharField(max_length=32, blank=True)
    submitted_code = models.CharField(max_length=128, blank=True)

    class Meta:
        db_table = 'core_verificationlog'


class Sale(models.Model):
    unit = models.ForeignKey('medicines.MedicineUnit', on_delete=models.PROTECT, related_name='sales')
    retailer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sales')
    quantity = models.PositiveIntegerField()
    sold_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_sale'
        ordering = ['-sold_at', '-id']
