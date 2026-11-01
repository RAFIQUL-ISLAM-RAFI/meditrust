from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User
from medicines.models import Medicine, Batch, MedicineUnit
from medicines.utils import generate_hash, generate_serial


class Command(BaseCommand):
    help = 'Create missing demo accounts and stock without resetting existing passwords or duplicating batches.'

    def handle(self, *args, **options):
        for name, role, password, organisation in [
            ('admin', 'ADMIN', 'admin123', 'MediTrust admin'),
            ('square', 'MANUFACTURER', 'pass1234', 'Square demo manufacturer'),
            ('lazz', 'RETAILER', 'pass1234', 'Lazz demo pharmacy'),
        ]:
            user, created = User.objects.get_or_create(username=name, defaults={
                'role': role, 'organization_name': organisation, 'is_verified': True,
                'is_staff': role == 'ADMIN', 'is_superuser': role == 'ADMIN',
            })
            if created:
                user.set_password(password)
                user.save()
        maker = User.objects.get(username='square')
        medicine, _ = Medicine.objects.get_or_create(name='Napa', generic_name='Paracetamol', manufacturer=maker)
        if not medicine.batches.exists():
            batch = Batch.objects.create(medicine=medicine, batch_number='B-2026-01',
                manufacture_date=timezone.localdate(), expiry_date=timezone.localdate() + timedelta(days=365))
            for _ in range(10):
                MedicineUnit.objects.create(unique_hash_code=generate_hash(), serial_number=generate_serial(),
                    current_owner=maker, batch=batch)
        self.stdout.write(self.style.SUCCESS('Demo accounts ready: admin/admin123, square/pass1234, lazz/pass1234. Existing passwords were preserved.'))
