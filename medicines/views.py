from urllib.parse import urlsplit
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from config.web import error_page, role_required
from tracking.models import OwnershipTransfer
from .forms import BatchForm, MedicineForm, QRAddressForm, RecallForm
from .models import Batch, MedicineUnit
from .utils import (batch_integrity_ok, batch_receive_url, generate_hash, generate_serial,
                    make_qr_png, public_base_url, unit_integrity_ok, unit_signature, unit_verify_url)


@role_required(User.Role.MANUFACTURER)
def manufacturer(request):
    batches = Batch.objects.filter(medicine__manufacturer=request.user).select_related('medicine').annotate(qty=Count('units')).order_by('-created_at')
    transfers = OwnershipTransfer.objects.filter(from_user=request.user, status='CONFIRMED')
    return render(request, 'ui/manufacturer.html', {'batches': batches, 'form': BatchForm(user=request.user),
        'total_units': MedicineUnit.objects.filter(batch__medicine__manufacturer=request.user).count(),
        'supplied': transfers.count(), 'active_batches': batches.filter(is_recalled=False, expiry_date__gte=timezone.localdate()).count(),
        'supply': transfers.values('to_user__username', 'to_user__organization_name').annotate(n=Count('id')).order_by('-n')})


@role_required(User.Role.MANUFACTURER)
def medicine_new(request):
    form = MedicineForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        medicine = form.save(commit=False)
        medicine.manufacturer = request.user
        medicine.save()
        messages.success(request, 'Medicine added. You can now create its first batch.')
        return redirect('ui:manufacturer')
    return render(request, 'ui/medicine_new.html', {'form': form})


@role_required(User.Role.MANUFACTURER)
def create_batch(request):
    form = BatchForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            batch = Batch.objects.create(medicine=data['medicine'], batch_number=data['batch_number'],
                manufacture_date=data['manufacture_date'], expiry_date=data['expiry_date'])
            units = [MedicineUnit(batch=batch, current_owner=request.user, unique_hash_code=generate_hash(),
                serial_number=generate_serial(), total_pills=data['tablets_per_unit']) for _ in range(data['total_quantity'])]
            for unit in units:
                unit.integrity_signature = unit_signature(unit)
            MedicineUnit.objects.bulk_create(units)
        messages.success(request, f"Created {len(units)} strips with signed QR codes.")
        return redirect('ui:qr_sheet', pk=batch.pk)
    return render(request, 'ui/form.html', {'form': form, 'title': 'Create a batch', 'back': reverse('ui:manufacturer')})


@role_required(User.Role.MANUFACTURER)
def qr_sheet(request, pk):
    batch = get_object_or_404(Batch, pk=pk, medicine__manufacturer=request.user)
    address = public_base_url(request)
    form = QRAddressForm(request.POST or None, initial={'base_url': address})
    if settings.PUBLIC_BASE_URL:
        form.fields['base_url'].disabled = True
    if request.method == 'POST' and form.is_valid():
        request.session['qr_base_url'] = form.cleaned_data['base_url']
        return redirect('ui:qr_sheet', pk=pk)
    return render(request, 'ui/qr_sheet.html', {'batch': batch, 'units': batch.units.all(), 'form': form,
        'qr_address': address, 'qr_locked': bool(settings.PUBLIC_BASE_URL),
        'loopback': urlsplit(address).hostname in ('localhost', '127.0.0.1', '::1')})


@login_required
def recall_batch(request, pk):
    batch = get_object_or_404(Batch.objects.select_related('medicine'), pk=pk)
    if not request.user.is_verified or not (request.user.role == 'ADMIN' or (
            request.user.role == 'MANUFACTURER' and batch.medicine.manufacturer_id == request.user.pk)):
        return error_page(request, 'Only the manufacturer of this batch or an administrator can recall it.')
    form = RecallForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        updated = Batch.objects.filter(pk=pk, is_recalled=False).update(is_recalled=True,
            recall_reason=form.cleaned_data['recall_reason'], recalled_at=timezone.now(), recalled_by=request.user)
        messages.success(request, 'Batch recalled. Every strip now shows a recall warning and sales are blocked.' if updated else 'This batch is already recalled.')
        return redirect('ui:dashboard')
    return render(request, 'ui/recall.html', {'batch': batch, 'form': form})


@role_required(User.Role.MANUFACTURER)
def unit_qr(request, code):
    unit = get_object_or_404(MedicineUnit.objects.select_related('batch__medicine'), unique_hash_code=code, batch__medicine__manufacturer=request.user)
    if not unit_integrity_ok(unit):
        return HttpResponse('Integrity check failed; QR issuance blocked.', status=409)
    return HttpResponse(make_qr_png(unit_verify_url(unit, request)), content_type='image/png')


@role_required(User.Role.MANUFACTURER)
def batch_qr(request, code):
    batch = get_object_or_404(Batch.objects.select_related('medicine'), batch_code=code, medicine__manufacturer=request.user)
    if not batch_integrity_ok(batch):
        return HttpResponse('Integrity check failed; QR issuance blocked.', status=409)
    return HttpResponse(make_qr_png(batch_receive_url(batch, request)), content_type='image/png')
