from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from config.web import error_page
from medicines.models import Batch, MedicineUnit
from tracking.models import VerificationLog
from .forms import RegisterForm, RoleAuthenticationForm
from .models import User


def home(request):
    return render(request, 'ui/landing.html')


@never_cache
def login_view(request, portal=None):
    roles = {'manufacturer': User.Role.MANUFACTURER, 'pharmacy': User.Role.RETAILER, 'admin': User.Role.ADMIN}
    if request.user.is_authenticated:
        return redirect('ui:dashboard')
    form = RoleAuthenticationForm(request, data=request.POST or None, expected_role=roles.get(portal))
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        target = request.POST.get('next', '')
        if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()):
            return redirect(target)
        return redirect('ui:dashboard')
    return render(request, 'ui/login.html', {'form': form, 'portal': portal,
        'portal_name': {'manufacturer': 'Manufacturer', 'pharmacy': 'Pharmacy / retailer', 'admin': 'Administrator'}.get(portal, ''),
        'next': request.POST.get('next', request.GET.get('next', ''))})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('ui:landing')


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.is_verified = False
        user.save()
        messages.success(request, 'Account created. An administrator must approve your organisation before you can manage stock.')
        return redirect('ui:login')
    return render(request, 'ui/register.html', {'form': form})


@login_required
def dashboard(request):
    if not request.user.is_verified:
        return render(request, 'ui/pending.html', status=403)
    if request.user.role == User.Role.MANUFACTURER:
        return redirect('ui:manufacturer')
    if request.user.role == User.Role.RETAILER:
        return redirect('ui:pharmacy')
    if request.user.role != User.Role.ADMIN:
        return error_page(request, 'This account has no recognised portal role.')
    return render(request, 'ui/admin.html', {
        'units_total': MedicineUnit.objects.count(),
        'users': User.objects.exclude(role='ADMIN'),
        'batches': Batch.objects.select_related('medicine__manufacturer').order_by('-id'),
        'suspicious': VerificationLog.objects.filter(is_suspicious=True).select_related('unit')[:50],
    })
