import hashlib
import io
import json
import uuid
from urllib.parse import urlencode, urlsplit
import qrcode
from django.conf import settings
from django.core import signing
from django.utils.crypto import constant_time_compare


def make_qr_png(url):
    qr = qrcode.QRCode(box_size=7, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color='black', back_color='white').save(buf, format='PNG')
    return buf.getvalue()


def batch_payload(batch):
    med = batch.medicine
    return {
        'version': 1, 'batch_code': batch.batch_code, 'batch_number': batch.batch_number,
        'expiry': batch.expiry_date.isoformat(),
        'manufactured': batch.manufacture_date.isoformat() if batch.manufacture_date else None,
        'medicine_id': batch.medicine_id, 'manufacturer_id': med.manufacturer_id,
        **{key: getattr(med, key, '') for key in (
            'name', 'generic_name', 'composition', 'description', 'side_effects', 'precautions', 'dosage_info')},
    }


def _signature(payload, salt):
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return signing.Signer(salt=salt).signature(canonical)


def batch_signature(batch):
    return _signature(batch_payload(batch), 'meditrust.batch.v1')


def unit_signature(unit):
    return _signature({**batch_payload(unit.batch), 'unit': unit.unique_hash_code,
                       'serial': unit.serial_number, 'total_pills': unit.total_pills}, 'meditrust.unit.v1')


def signature_matches(value, expected):
    return bool(value and expected and constant_time_compare(value, expected))


def batch_integrity_ok(batch):
    return signature_matches(batch.integrity_signature, batch_signature(batch))


def unit_integrity_ok(unit):
    return batch_integrity_ok(unit.batch) and signature_matches(unit.integrity_signature, unit_signature(unit))


def normalize_base_url(value):
    p = urlsplit(value.strip())
    if p.scheme not in ('http', 'https') or not p.netloc or not p.hostname:
        raise ValueError('Enter a full website address beginning with http:// or https://.')
    if p.username or p.password or p.query or p.fragment or p.path not in ('', '/'):
        raise ValueError('Use only the website origin, for example https://meditrust.example.com.')
    try:
        p.port
    except ValueError as exc:
        raise ValueError('The port number is invalid.') from exc
    return f'{p.scheme}://{p.netloc}'.rstrip('/')


def public_base_url(request):
    configured = settings.PUBLIC_BASE_URL or request.session.get('qr_base_url', '')
    return normalize_base_url(configured or request.build_absolute_uri('/'))


def unit_verify_path(unit):
    return f'/verify/{unit.unique_hash_code}/?' + urlencode({'sig': unit.integrity_signature})


def unit_verify_url(unit, request):
    return public_base_url(request) + unit_verify_path(unit)


def batch_receive_url(batch, request):
    return public_base_url(request) + f'/receive/{batch.batch_code}/?' + urlencode({'sig': batch.integrity_signature})


def generate_hash():
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:32]


def generate_serial():
    return 'MT-' + uuid.uuid4().hex[:10].upper()
