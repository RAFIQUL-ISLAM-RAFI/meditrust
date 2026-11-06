from datetime import timedelta
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TransactionTestCase
from django.utils import timezone
from medicines.utils import batch_signature, unit_signature, unit_integrity_ok


class ThreeAppMigrationTests(TransactionTestCase):
    """Exercise the upgrade with real pre-split rows, grants and sessions."""
    old_target = ('core', '0003_seal_existing_records')

    def setUp(self):
        self.addCleanup(self.migrate_latest)
        executor = MigrationExecutor(connection)
        executor.migrate([self.old_target, ('medicines', None), ('tracking', None)])
        executor = MigrationExecutor(connection)
        self.old_apps = executor.loader.project_state([
            self.old_target, ('admin', '0003_logentry_add_action_flag_choices'),
            ('sessions', '0001_initial'),
        ]).apps

    def migrate_latest(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def make_legacy_data(self):
        get = lambda name: self.old_apps.get_model('core', name)
        User = get('User')
        maker = User.objects.create(username='legacy-maker', password=make_password('Kept-Password-42!'),
                                    role='MANUFACTURER', is_verified=True)
        retailer = User.objects.create(username='legacy-pharmacy', password=make_password('Kept-Password-42!'),
                                       role='RETAILER', is_verified=True)
        medicine = get('Medicine').objects.create(name='Legacy medicine', generic_name='Legacy generic',
                                                   manufacturer=maker, description='Existing guidance')
        batch = get('Batch').objects.create(medicine=medicine, batch_number='LEGACY-123',
                                            manufacture_date=timezone.localdate(),
                                            expiry_date=timezone.localdate() + timedelta(days=365))
        batch.integrity_signature = batch_signature(batch)
        batch.save(update_fields=['integrity_signature'])
        unit = get('MedicineUnit').objects.create(batch=batch, current_owner=retailer, sold_pills=3,
                                                  unique_hash_code='legacy-unit-code', serial_number='MT-LEGACY1234',
                                                  first_public_visitor='existing-browser',
                                                  first_public_check=timezone.now(), duplicate_detected=True)
        unit.integrity_signature = unit_signature(unit)
        unit.save(update_fields=['integrity_signature'])
        get('OwnershipTransfer').objects.create(unit=unit, from_user=maker, to_user=retailer,
                                                status='CONFIRMED', confirmed_at=timezone.now())
        get('Sale').objects.create(unit=unit, retailer=retailer, quantity=3)
        get('VerificationLog').objects.create(unit=unit, submitted_code=unit.unique_hash_code,
                                               verification_result='REUSED_CODE', is_suspicious=True)
        ContentType = self.old_apps.get_model('contenttypes', 'ContentType')
        Permission = self.old_apps.get_model('auth', 'Permission')
        Group = self.old_apps.get_model('auth', 'Group')
        content_type, _ = ContentType.objects.get_or_create(app_label='core', model='medicine')
        permission, _ = Permission.objects.get_or_create(content_type=content_type, codename='view_medicine',
                                                          defaults={'name': 'Can view medicine'})
        maker.user_permissions.add(permission)
        group = Group.objects.create(name='Legacy medicine readers')
        group.permissions.add(permission)
        retailer.groups.add(group)
        self.old_apps.get_model('admin', 'LogEntry').objects.create(
            user=maker, content_type=content_type, object_id=str(medicine.pk),
            object_repr='Legacy medicine', action_flag=2, change_message='Existing history',
        )
        return maker, retailer, batch, unit, content_type, permission, group

    def snapshot_domain_rows(self):
        names = ['user', 'medicine', 'batch', 'medicineunit', 'ownershiptransfer', 'verificationlog', 'sale']
        with connection.cursor() as cursor:
            result = {}
            for name in names:
                cursor.execute('SELECT * FROM ' + connection.ops.quote_name('core_' + name) + ' ORDER BY id')
                result[name] = cursor.fetchall()
            return result

    def test_existing_rows_passwords_signatures_permissions_and_sessions_survive(self):
        maker, retailer, batch, unit, content_type, permission, group = self.make_legacy_data()
        from accounts.models import User
        client = Client()
        client.force_login(User.objects.get(pk=retailer.pk))
        before = self.snapshot_domain_rows()
        self.migrate_latest()
        self.assertEqual(self.snapshot_domain_rows(), before)
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth.models import Permission
        from django.contrib.admin.models import LogEntry
        from medicines.models import Batch, MedicineUnit
        kept = MedicineUnit.objects.select_related('batch__medicine').get(pk=unit.pk)
        self.assertEqual(kept.integrity_signature, unit.integrity_signature)
        self.assertEqual(Batch.objects.get(pk=batch.pk).integrity_signature, batch.integrity_signature)
        self.assertTrue(unit_integrity_ok(kept))
        self.assertEqual(ContentType.objects.get(pk=content_type.pk).app_label, 'medicines')
        self.assertEqual(Permission.objects.get(pk=permission.pk).content_type_id, content_type.pk)
        self.assertEqual(LogEntry.objects.get(change_message='Existing history').content_type_id, content_type.pk)
        self.assertTrue(User.objects.get(pk=maker.pk).has_perm('medicines.view_medicine'))
        self.assertTrue(User.objects.get(pk=retailer.pk).has_perm('medicines.view_medicine'))
        self.assertTrue(User.objects.get(pk=retailer.pk).check_password('Kept-Password-42!'))
        self.assertEqual(client.get('/pharmacy/').status_code, 200)
        self.assertEqual(Client().get('/api/verify/legacy-unit-code/', {'sig': unit.integrity_signature}).json()['status'], 'REUSED_CODE')
        if connection.vendor == 'sqlite':
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA foreign_key_check')
                self.assertEqual(cursor.fetchall(), [])

    def test_partial_migration_content_types_merge_without_losing_grants(self):
        maker, retailer, batch, unit, old_type, old_permission, group = self.make_legacy_data()
        ContentType = self.old_apps.get_model('contenttypes', 'ContentType')
        Permission = self.old_apps.get_model('auth', 'Permission')
        new_type = ContentType.objects.create(app_label='medicines', model='medicine')
        new_permission = Permission.objects.create(content_type=new_type, codename='change_medicine', name='Can change medicine')
        maker.user_permissions.add(new_permission)
        group.permissions.add(new_permission)
        self.old_apps.get_model('admin', 'LogEntry').objects.create(
            user=maker, content_type=new_type, object_id='1', object_repr='Partial migrate entry',
            action_flag=2, change_message='Partial history',
        )
        self.migrate_latest()
        from accounts.models import User
        from django.contrib.contenttypes.models import ContentType as CurrentContentType
        from django.contrib.admin.models import LogEntry
        self.assertEqual(CurrentContentType.objects.get(app_label='medicines', model='medicine').pk, old_type.pk)
        self.assertEqual(LogEntry.objects.get(change_message='Partial history').content_type_id, old_type.pk)
        self.assertTrue(User.objects.get(pk=maker.pk).has_perm('medicines.change_medicine'))
        self.assertTrue(User.objects.get(pk=retailer.pk).has_perm('medicines.change_medicine'))

