import secrets
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from accounts.models import User
from config.web import error_page, role_required
from medicines.models import Batch, MedicineUnit
from medicines.utils import batch_integrity_ok, signature_matches, unit_integrity_ok
from .forms import TransferForm
from .models import OwnershipTransfer, Sale, VerificationLog


@role_required(User.Role.MANUFACTURER)
def transfer_batch(request, pk):
    batch = get_object_or_404(Batch.objects.select_related('medicine'), pk=pk, medicine__manufacturer=request.user)
    if batch.is_recalled or batch.is_expired or not batch_integrity_ok(batch):
        return error_page(request, 'Recalled, expired or altered batches cannot be transferred.', 400)
    form = TransferForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            units = list(batch.units.filter(current_owner=request.user).exclude(transfers__status='PENDING'))
            if not units:
                form.add_error(None, 'No eligible strips remain. This batch may already be supplied or pending receipt.')
            elif not all(unit_integrity_ok(u) for u in units):
                form.add_error(None, 'A strip failed its integrity check. This transfer was blocked.')
            else:
                OwnershipTransfer.objects.bulk_create([OwnershipTransfer(unit=u, from_user=request.user, to_user=form.cleaned_data['retailer']) for u in units])
                messages.success(request, f'Sent {len(units)} strips for pharmacy confirmation.')
                return redirect('ui:manufacturer')
    return render(request, 'ui/form.html', {'form': form, 'title': f'Transfer {batch.batch_number}', 'back': reverse('ui:manufacturer')})


@role_required(User.Role.RETAILER)
def pharmacy(request):
    owned = MedicineUnit.objects.filter(current_owner=request.user).select_related('batch__medicine').order_by('-id')
    stock = owned.filter(sold_pills__lt=F('total_pills'), batch__is_recalled=False, batch__expiry_date__gte=timezone.localdate())
    query = request.GET.get('q', '').strip()
    shown = owned.filter(Q(serial_number__icontains=query) | Q(batch__medicine__name__icontains=query) | Q(batch__batch_number__icontains=query)) if query else owned
    pending = OwnershipTransfer.objects.filter(to_user=request.user, status='PENDING').values('unit__batch__batch_code', 'unit__batch__batch_number', 'from_user__username').annotate(n=Count('id'))
    return render(request, 'ui/pharmacy.html', {'page_obj': Paginator(shown, 25).get_page(request.GET.get('page')),
        'stock_count': stock.count(), 'tablets_left': stock.aggregate(n=Sum(F('total_pills') - F('sold_pills')))['n'] or 0,
        'pending': pending, 'q': query})


@role_required(User.Role.RETAILER)
def receive_scan(request):
    error = ''
    if request.method == 'POST':
        value = request.POST.get('code', '').strip()
        batches = Batch.objects.filter(units__transfers__to_user=request.user, units__transfers__status='PENDING').filter(Q(batch_code__iexact=value) | Q(batch_number__iexact=value)).distinct()
        if batches.count() == 1:
            request.session['manual_receive_batch'] = batches.first().batch_code
            return redirect('ui:receive_confirm', code=batches.first().batch_code)
        error = 'No unique pending delivery matches that code. Scan the signed carton QR or check the number with the manufacturer.'
    return render(request, 'ui/receive.html', {'error': error})


@role_required(User.Role.RETAILER)
def receive_confirm(request, code):
    batch = get_object_or_404(Batch.objects.select_related('medicine__manufacturer'), batch_code=code)
    pending = OwnershipTransfer.objects.filter(unit__batch=batch, to_user=request.user, status='PENDING')
    manual = request.session.get('manual_receive_batch') == code
    valid = signature_matches(request.GET.get('sig', ''), batch.integrity_signature)
    if not batch_integrity_ok(batch) or not (valid or manual):
        return error_page(request, 'This carton QR is unsigned, altered or no longer matches its registered details. Ask the manufacturer for a current QR.', 400)
    if batch.is_recalled or batch.is_expired:
        return error_page(request, 'This delivery is recalled or expired. Receipt has been blocked.', 400)
    count = pending.count()
    if request.method == 'POST':
        with transaction.atomic():
            units = list(MedicineUnit.objects.filter(pk__in=pending.values('unit_id'), current_owner_id=F('batch__medicine__manufacturer_id')).select_related('batch__medicine'))
            if not units or len(units) != count or not all(unit_integrity_ok(u) for u in units):
                return error_page(request, 'No valid pending delivery remains. No stock was moved.', 400)
            ids = [u.pk for u in units]
            MedicineUnit.objects.filter(pk__in=ids).update(current_owner=request.user)
            pending.filter(unit_id__in=ids).update(status='CONFIRMED', confirmed_at=timezone.now())
        request.session.pop('manual_receive_batch', None)
        messages.success(request, f'Received {count} strips into your pharmacy.')
        return redirect('ui:pharmacy')
    return render(request, 'ui/receive_confirm.html', {'batch': batch, 'qty': count})


@role_required(User.Role.RETAILER)
@require_POST
def sell(request, code):
    try:
        qty = int(request.POST.get('qty', request.POST.get('tablets', 0)))
    except (ValueError, TypeError):
        qty = 0
    with transaction.atomic():
        unit = get_object_or_404(MedicineUnit.objects.select_related('batch__medicine'), unique_hash_code=code)
        if unit.current_owner_id != request.user.pk:
            return error_page(request, 'You can only record sales from your own pharmacy stock.')
        if not unit_integrity_ok(unit):
            messages.error(request, 'Sale blocked: the registered details failed their integrity check.')
        elif unit.batch.is_recalled:
            messages.error(request, 'Sale blocked: this batch has been recalled.')
        elif unit.batch.is_expired:
            messages.error(request, 'Sale blocked: this medicine has expired.')
        elif qty < 1 or qty > unit.remaining:
            messages.error(request, f'Enter a quantity from 1 to {unit.remaining}.')
        else:
            updated = MedicineUnit.objects.filter(pk=unit.pk, current_owner=request.user,
                sold_pills__lte=F('total_pills') - qty, batch__is_recalled=False,
                batch__expiry_date__gte=timezone.localdate()).update(sold_pills=F('sold_pills') + qty)
            if updated:
                Sale.objects.create(unit=unit, retailer=request.user, quantity=qty)
                messages.success(request, f'Recorded a sale of {qty} tablets.')
            else:
                messages.error(request, 'Stock or batch status changed. Reload before recording the sale.')
    return redirect('ui:pharmacy')


@role_required(User.Role.RETAILER)
def sales(request):
    rows = Sale.objects.filter(retailer=request.user).select_related('unit__batch__medicine')
    return render(request, 'ui/sales.html', {'page_obj': Paginator(rows, 30).get_page(request.GET.get('page')),
        'total': rows.aggregate(n=Sum('quantity'))['n'] or 0})


def _trusted_operator(request, unit):
    return request.user.is_authenticated and request.user.is_verified and (
        request.user.role == 'ADMIN' or request.user.pk in (unit.current_owner_id, unit.batch.medicine.manufacturer_id))


def build_result(request, unit, *, signature='', manual=False, submitted_code=''):
    visitor = request.session.get('verification_visitor')
    if not visitor:
        visitor = secrets.token_urlsafe(24)
        request.session['verification_visitor'] = visitor
    fingerprint = salted_hmac('meditrust.visitor', visitor).hexdigest()
    operator = bool(unit and _trusted_operator(request, unit))
    if not unit:
        status, title, text, tone = 'NOT_FOUND', 'Code not found', 'This code does not match a MediTrust record. Check for typing errors and ask the pharmacy to verify the source. This result alone does not prove a product is counterfeit.', 'warn'
    elif not unit_integrity_ok(unit):
        status, title, text, tone = 'TAMPERED', 'Details could not be verified', 'The registered medicine or batch details no longer match their issued signature. Ask the pharmacy or manufacturer to investigate before using this pack.', 'bad'
    elif signature and not signature_matches(signature, unit.integrity_signature):
        status, title, text, tone = 'INVALID_SIGNATURE', 'QR signature does not match', 'This QR link was altered or belongs to a different record. Scan the original label and ask the pharmacy to verify it.', 'bad'
    elif unit.batch.is_recalled:
        status, title, text, tone = 'RECALLED', 'Batch recalled', 'This batch has been recalled. Do not use it; contact the pharmacy for return instructions.', 'bad'
    elif unit.batch.is_expired:
        status, title, text, tone = 'EXPIRED', 'Medicine expired', 'This batch is past its registered expiry date. Do not use it; contact the pharmacy.', 'bad'
    elif unit.remaining <= 0:
        status, title, text, tone = 'SOLD_OUT', 'Already sold', 'All tablets in this strip have been recorded as sold. This is a sale status, not proof of counterfeiting. If it is being offered for sale again, ask the pharmacy to check it.', 'warn'
    elif not signature_matches(signature, unit.integrity_signature) and not operator:
        status, title, text, tone = 'SERIAL_MATCH' if manual else 'UNSIGNED', 'Registered serial' if manual else 'Unsigned QR link', 'The serial matches a registered record, but this lookup does not check the printed QR signature. Scan the current signed label for the full check.', 'warn'
    else:
        if not operator:
            with transaction.atomic():
                MedicineUnit.objects.filter(pk=unit.pk, first_public_visitor='').update(first_public_visitor=fingerprint, first_public_check=timezone.now())
                unit.refresh_from_db(fields=['first_public_visitor', 'duplicate_detected'])
                if unit.first_public_visitor != fingerprint:
                    MedicineUnit.objects.filter(pk=unit.pk).update(duplicate_detected=True)
                    unit.duplicate_detected = True
        if unit.duplicate_detected:
            status, title, text, tone = 'REUSED_CODE', 'Code checked on another browser', 'This signed code has been checked from more than one browser. It may have been shared or copied. Ask the pharmacy to confirm the pack and its source; this alert is not proof of a fake.', 'warn'
        elif operator and not signature:
            status, title, text, tone = 'STOCK_RECORD', 'Registered stock record', 'These registered details match their issued data signature. This is your operational stock view; scan the printed QR to check a label.', 'ok'
        else:
            status, title, text, tone = 'VERIFIED', 'Registered medicine', 'The QR signature matches the registered details. The batch is in date and not recalled. Compare these details with the pack; a matching code alone cannot prove the physical contents are genuine.', 'ok'
    count = unit.logs.count() if unit else 0
    if not operator:
        count += 1
        VerificationLog.objects.create(unit=unit, location=request.META.get('REMOTE_ADDR', '')[:100], scan_count=count,
            is_suspicious=status in ('TAMPERED', 'INVALID_SIGNATURE', 'REUSED_CODE', 'NOT_FOUND'),
            visitor_fingerprint=fingerprint, verification_result=status, submitted_code=submitted_code[:128])
    return {'status': status, 'title': title, 'text': text, 'tone': tone, 'scan_count': count}


@never_cache
def verify(request, code):
    unit = MedicineUnit.objects.select_related('batch__medicine__manufacturer', 'current_owner').filter(unique_hash_code=code).first()
    manual = request.session.get('manual_lookup') == code
    result = build_result(request, unit, signature=request.GET.get('sig', ''), manual=manual, submitted_code=code)
    can_sell = bool(unit and request.user.is_authenticated and request.user.is_verified and request.user.role == 'RETAILER'
        and unit.current_owner_id == request.user.pk and unit.remaining > 0 and not unit.batch.is_expired
        and not unit.batch.is_recalled and unit_integrity_ok(unit) and result['status'] != 'INVALID_SIGNATURE')
    return render(request, 'ui/verify.html', {'result': result, 'unit': unit, 'can_sell': can_sell})


def scan(request):
    error = ''
    value = request.POST.get('code', request.POST.get('serial', request.GET.get('serial', ''))).strip().upper()
    if request.method == 'POST' or request.GET.get('serial'):
        unit = MedicineUnit.objects.filter(serial_number=value).first()
        if unit:
            request.session['manual_lookup'] = unit.unique_hash_code
            return redirect('ui:verify', code=unit.unique_hash_code)
        error = 'No registered serial matches that entry. Check the characters printed under the QR.'
        VerificationLog.objects.create(submitted_code=value[:128], verification_result='NOT_FOUND',
            is_suspicious=True, location=request.META.get('REMOTE_ADDR', '')[:100])
    return render(request, 'ui/scan.html', {'error': error, 'code': value})


@never_cache
def api_verify(request, code):
    unit = MedicineUnit.objects.select_related('batch__medicine__manufacturer', 'current_owner').filter(unique_hash_code=code).first()
    result = build_result(request, unit, signature=request.GET.get('sig', ''), submitted_code=code)
    data = {'status': result['status'], 'title': result['title'], 'message': result['text'], 'scan_count': result['scan_count']}
    if unit:
        data.update(medicine=unit.batch.medicine.name, generic_name=unit.batch.medicine.generic_name,
            manufacturer=str(unit.batch.medicine.manufacturer), batch_number=unit.batch.batch_number,
            expiry_date=unit.batch.expiry_date.isoformat(), owner=str(unit.current_owner),
            sold=unit.sold_pills, remaining=unit.remaining, serial=unit.serial_number, recalled=unit.batch.is_recalled)
    return JsonResponse(data)
