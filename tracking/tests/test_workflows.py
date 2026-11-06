from datetime import timedelta
from urllib.parse import urlencode
from django.contrib import admin
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from medicines.models import Batch, Medicine, MedicineUnit
from tracking.models import OwnershipTransfer, Sale, VerificationLog
from medicines.utils import batch_receive_url, generate_hash, generate_serial, unit_integrity_ok, unit_verify_path, unit_verify_url


class MediTrustWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maker = User.objects.create_user('maker', password='TestPassword1!', role='MANUFACTURER')
        cls.other_maker = User.objects.create_user('othermaker', password='TestPassword1!', role='MANUFACTURER')
        cls.retailer = User.objects.create_user('retailer', password='TestPassword1!', role='RETAILER')
        cls.other_retailer = User.objects.create_user('otherretailer', password='TestPassword1!', role='RETAILER')
        cls.admin = User.objects.create_superuser('superadmin', password='TestPassword1!')
        cls.med = Medicine.objects.create(name='Test medicine', generic_name='Test generic', manufacturer=cls.maker)
        cls.batch = Batch.objects.create(medicine=cls.med, batch_number='TEST-001',
            manufacture_date=timezone.localdate(), expiry_date=timezone.localdate() + timedelta(days=365))
        cls.unit = MedicineUnit.objects.create(batch=cls.batch, current_owner=cls.retailer,
            unique_hash_code=generate_hash(), serial_number=generate_serial())

    def authenticated(self, user):
        client = Client()
        client.force_login(user)
        return client

    def api_url(self, unit=None, signature=None):
        unit = unit or self.unit
        signature = unit.integrity_signature if signature is None else signature
        return reverse('ui:api_verify', args=[unit.unique_hash_code]) + '?' + urlencode({'sig': signature})

    def test_landing_and_logo_have_real_home(self):
        response = self.client.get('/')
        self.assertContains(response, 'MediTrust')
        self.assertContains(response, 'href="/scan/"')
        self.assertEqual(self.authenticated(self.maker).get('/').status_code, 200)

    def test_scanner_is_local_and_has_camera_upload_and_serial_controls(self):
        response = self.client.get('/scan/')
        for value in ['id="start"', 'id="stop"', 'id="qr-file"', 'html5-qrcode-2.3.8.min.js', 'ui/scan.js', 'name="code"']:
            self.assertContains(response, value)
        self.assertNotContains(response, 'unpkg.com')

    def test_portal_login_rejects_wrong_role(self):
        response = self.client.post('/login/manufacturer/', {'username': 'retailer', 'password': 'TestPassword1!'})
        self.assertContains(response, 'different portal')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.post('/login/pharmacy/', {'username': 'retailer', 'password': 'TestPassword1!'}).status_code, 302)

    def test_open_redirect_is_rejected(self):
        response = self.client.post('/login/manufacturer/', {'username': 'maker', 'password': 'TestPassword1!', 'next': 'https://untrusted.example/'})
        self.assertEqual(response['Location'], '/dashboard/')

    def test_role_boundaries_and_pending_accounts(self):
        self.assertEqual(self.authenticated(self.retailer).get('/manufacturer/').status_code, 403)
        self.assertEqual(self.authenticated(self.maker).get('/pharmacy/').status_code, 403)
        self.retailer.is_verified = False
        self.retailer.save()
        self.assertContains(self.authenticated(self.retailer).get('/pharmacy/'), 'Approval pending', status_code=403)

    def test_superuser_role_and_admin_registration(self):
        self.assertEqual(self.admin.role, 'ADMIN')
        self.assertIn(User, admin.site._registry)
        self.assertIn(Batch, admin.site._registry)
        self.assertContains(self.authenticated(self.admin).get('/dashboard/'), 'Admin overview')

    def test_qr_uses_request_origin_and_has_signature(self):
        client = self.authenticated(self.maker)
        request = client.get(reverse('ui:qr_sheet', args=[self.batch.pk]), HTTP_HOST='192.168.1.20:8000').wsgi_request
        url = unit_verify_url(self.unit, request)
        self.assertTrue(url.startswith('http://192.168.1.20:8000/verify/'))
        self.assertIn(self.unit.integrity_signature, url)
        self.assertTrue(batch_receive_url(self.batch, request).startswith('http://192.168.1.20:8000/receive/'))

    @override_settings(PUBLIC_BASE_URL='https://meditrust.example.com')
    def test_public_qr_origin_can_be_configured(self):
        request = self.authenticated(self.maker).get('/manufacturer/').wsgi_request
        self.assertTrue(unit_verify_url(self.unit, request).startswith('https://meditrust.example.com/'))
        response = self.authenticated(self.maker).get(reverse('ui:qr_sheet', args=[self.batch.pk]))
        self.assertTrue(response.context['form'].fields['base_url'].disabled)

    def test_manufacturer_can_set_qr_address_and_generate_real_png(self):
        client = self.authenticated(self.maker)
        client.post(reverse('ui:qr_sheet', args=[self.batch.pk]), {'base_url': 'http://192.168.1.20:8000'})
        self.assertEqual(client.session['qr_base_url'], 'http://192.168.1.20:8000')
        png = client.get(reverse('ui:unit_qr', args=[self.unit.unique_hash_code]))
        self.assertEqual(png.status_code, 200)
        self.assertTrue(png.content.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual(self.authenticated(self.other_maker).get(reverse('ui:unit_qr', args=[self.unit.unique_hash_code])).status_code, 404)

    def test_signed_qr_and_same_browser_reload_remain_verified(self):
        for _ in range(32):
            self.assertEqual(self.client.get(self.api_url()).json()['status'], 'VERIFIED')
        self.unit.refresh_from_db()
        self.assertFalse(self.unit.duplicate_detected)
        self.assertEqual(self.unit.sold_pills, 0)

    def test_second_browser_flags_copied_or_shared_code(self):
        self.assertEqual(self.client.get(self.api_url()).json()['status'], 'VERIFIED')
        self.assertEqual(Client().get(self.api_url()).json()['status'], 'REUSED_CODE')
        self.assertEqual(self.client.get(self.api_url()).json()['status'], 'REUSED_CODE')

    def test_owner_checks_do_not_claim_customer_code(self):
        self.assertEqual(self.authenticated(self.retailer).get(self.api_url()).json()['status'], 'VERIFIED')
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.first_public_visitor, '')
        self.assertEqual(self.unit.logs.count(), 0)
        self.assertEqual(self.client.get(self.api_url()).json()['status'], 'VERIFIED')

    def test_internal_stock_link_is_explained_without_claiming_a_scanned_qr(self):
        response = self.authenticated(self.retailer).get(reverse('ui:verify', args=[self.unit.unique_hash_code]))
        self.assertContains(response, 'Registered stock record')
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.first_public_visitor, '')

    def test_changed_qr_signature_is_rejected(self):
        self.assertEqual(self.client.get(self.api_url(signature='altered')).json()['status'], 'INVALID_SIGNATURE')

    def test_unsigned_link_does_not_claim_signature_verified(self):
        self.assertEqual(self.client.get(self.api_url(signature='')).json()['status'], 'UNSIGNED')

    def test_database_metadata_change_is_detected(self):
        Medicine.objects.filter(pk=self.med.pk).update(name='Changed medicine')
        self.assertEqual(self.client.get(self.api_url()).json()['status'], 'TAMPERED')
        self.assertEqual(self.authenticated(self.maker).get(reverse('ui:unit_qr', args=[self.unit.unique_hash_code])).status_code, 409)

    def test_tampered_expiry_is_detected(self):
        Batch.objects.filter(pk=self.batch.pk).update(expiry_date=timezone.localdate() + timedelta(days=500))
        self.assertEqual(self.client.get(self.api_url()).json()['status'], 'TAMPERED')

    def test_expired_stock_cannot_be_sold_or_show_sale_form(self):
        batch = Batch.objects.create(medicine=self.med, batch_number='OLD', expiry_date=timezone.localdate()-timedelta(days=1))
        unit = MedicineUnit.objects.create(batch=batch, current_owner=self.retailer, unique_hash_code=generate_hash(), serial_number=generate_serial())
        client = self.authenticated(self.retailer)
        self.assertNotContains(client.get(unit_verify_path(unit)), 'Confirm sale')
        response = client.post(reverse('ui:sell', args=[unit.unique_hash_code]), {'qty': 1}, follow=True)
        self.assertContains(response, 'Sale blocked')
        unit.refresh_from_db()
        self.assertEqual(unit.sold_pills, 0)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(self.client.get(self.api_url(unit)).json()['status'], 'EXPIRED')

    def test_recall_warns_existing_qr_and_blocks_sales(self):
        maker = self.authenticated(self.maker)
        self.assertEqual(maker.post(reverse('ui:recall_batch', args=[self.batch.pk]), {'recall_reason': 'Packaging issue'}).status_code, 302)
        self.assertEqual(self.client.get(self.api_url()).json()['status'], 'RECALLED')
        self.assertContains(self.client.get(unit_verify_path(self.unit)), 'Packaging issue')
        self.authenticated(self.retailer).post(reverse('ui:sell', args=[self.unit.unique_hash_code]), {'qty': 1})
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.sold_pills, 0)
        self.assertEqual(maker.get(reverse('ui:transfer_batch', args=[self.batch.pk])).status_code, 400)

    def test_foreign_manufacturer_or_retailer_cannot_recall_batch(self):
        for user in [self.other_maker, self.retailer]:
            self.assertEqual(self.authenticated(user).post(reverse('ui:recall_batch', args=[self.batch.pk]), {'recall_reason': 'Not allowed'}).status_code, 403)
        self.batch.refresh_from_db()
        self.assertFalse(self.batch.is_recalled)

    def test_admin_can_recall_and_reason_is_required(self):
        client = self.authenticated(self.admin)
        response = client.post(reverse('ui:recall_batch', args=[self.batch.pk]), {'recall_reason': ''})
        self.assertContains(response, 'This field is required')
        client.post(reverse('ui:recall_batch', args=[self.batch.pk]), {'recall_reason': 'Admin recall'})
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.recalled_by, self.admin)

    def test_sale_changes_stock_and_records_history_without_invalidating_signature(self):
        client = self.authenticated(self.retailer)
        client.post(reverse('ui:sell', args=[self.unit.unique_hash_code]), {'qty': 3})
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.remaining, 7)
        self.assertTrue(unit_integrity_ok(self.unit))
        self.assertEqual(Sale.objects.get(unit=self.unit).quantity, 3)
        self.assertContains(client.get('/pharmacy/sales/'), self.unit.serial_number)

    def test_sale_rejects_negative_excess_and_foreign_stock(self):
        for qty in [-1, 0, 11, 'bad']:
            self.authenticated(self.retailer).post(reverse('ui:sell', args=[self.unit.unique_hash_code]), {'qty': qty})
        self.assertEqual(self.authenticated(self.other_retailer).post(reverse('ui:sell', args=[self.unit.unique_hash_code]), {'qty': 1}).status_code, 403)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.sold_pills, 0)

    def test_sold_and_unknown_messages_do_not_claim_fake(self):
        MedicineUnit.objects.filter(pk=self.unit.pk).update(sold_pills=10)
        result = self.client.get(self.api_url()).json()
        self.assertEqual(result['status'], 'SOLD_OUT')
        self.assertIn('not proof of counterfeiting', result['message'])
        unknown = self.client.get('/api/verify/no-such-code/').json()
        self.assertEqual(unknown['status'], 'NOT_FOUND')
        self.assertTrue(VerificationLog.objects.filter(unit=None, submitted_code='no-such-code').exists())

    def test_transfer_receive_requires_correct_signed_carton_and_pharmacy(self):
        MedicineUnit.objects.filter(pk=self.unit.pk).update(current_owner=self.maker)
        self.authenticated(self.maker).post(reverse('ui:transfer_batch', args=[self.batch.pk]), {'retailer': self.retailer.pk})
        self.assertEqual(OwnershipTransfer.objects.filter(unit=self.unit, status='PENDING').count(), 1)
        url = reverse('ui:receive_confirm', args=[self.batch.batch_code]) + '?' + urlencode({'sig': self.batch.integrity_signature})
        self.assertEqual(self.authenticated(self.retailer).get(url.replace(self.batch.integrity_signature, 'changed')).status_code, 400)
        self.assertEqual(self.authenticated(self.other_retailer).post(url).status_code, 400)
        self.assertEqual(self.authenticated(self.retailer).post(url).status_code, 302)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.current_owner, self.retailer)
        self.assertTrue(unit_integrity_ok(self.unit))

    def test_recalled_delivery_cannot_be_received(self):
        MedicineUnit.objects.filter(pk=self.unit.pk).update(current_owner=self.maker)
        OwnershipTransfer.objects.create(unit=self.unit, from_user=self.maker, to_user=self.retailer)
        Batch.objects.filter(pk=self.batch.pk).update(is_recalled=True, recall_reason='Recall')
        url = reverse('ui:receive_confirm', args=[self.batch.batch_code]) + '?' + urlencode({'sig': self.batch.integrity_signature})
        self.assertEqual(self.authenticated(self.retailer).post(url).status_code, 400)

    def test_serial_fallback_does_not_bypass_signed_qr_claim(self):
        response = self.client.post('/scan/', {'code': self.unit.serial_number}, follow=True)
        self.assertContains(response, 'Registered serial')
        self.assertNotContains(response, 'Registered medicine</h1>')

    def test_batch_creation_persists_real_fields_and_sigs(self):
        client = self.authenticated(self.maker)
        response = client.post('/manufacturer/batch/new/', {'medicine': self.med.pk, 'batch_number': 'NEW', 'total_quantity': 2,
            'tablets_per_unit': 14, 'manufacture_date': timezone.localdate(), 'expiry_date': timezone.localdate()+timedelta(days=30)})
        self.assertEqual(response.status_code, 302)
        batch = Batch.objects.get(batch_number='NEW')
        self.assertEqual(batch.units.count(), 2)
        self.assertTrue(all(unit_integrity_ok(u) and u.total_pills == 14 for u in batch.units.all()))

    def test_invalid_batch_form_keeps_values_and_error(self):
        client = self.authenticated(self.maker)
        response = client.post('/manufacturer/batch/new/', {'medicine': self.med.pk, 'batch_number': 'KEEP-ME', 'total_quantity': 2,
            'tablets_per_unit': 10, 'manufacture_date': timezone.localdate(), 'expiry_date': timezone.localdate()-timedelta(days=1)})
        self.assertContains(response, 'Expiry date cannot be in the past')
        self.assertContains(response, 'KEEP-ME')
        self.assertFalse(Batch.objects.filter(batch_number='KEEP-ME').exists())

    def test_registration_cannot_create_verified_admin(self):
        response = self.client.post('/register/', {'role': 'MANUFACTURER', 'organization_name': 'Test org', 'license_no': 'L-001',
            'address': 'Test address', 'email': 'test@example.com', 'username': 'neworganisation',
            'password1': 'Frosty-Mango-72!Blue', 'password2': 'Frosty-Mango-72!Blue'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.get(username='neworganisation').is_verified)

    def test_registration_rejects_admin_role(self):
        response = self.client.post('/register/', {'role': 'ADMIN', 'organization_name': 'Test org', 'license_no': 'L-001',
            'address': 'Test address', 'email': 'test@example.com', 'username': 'publicadmin',
            'password1': 'Frosty-Mango-72!Blue', 'password2': 'Frosty-Mango-72!Blue'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='publicadmin').exists())

    def test_state_changing_sale_is_csrf_protected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.retailer)
        self.assertEqual(client.post(reverse('ui:sell', args=[self.unit.unique_hash_code]), {'qty': 1}).status_code, 403)
