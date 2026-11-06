from django import forms
from accounts.models import User


class TransferForm(forms.Form):
    retailer = forms.ModelChoiceField(queryset=User.objects.filter(role='RETAILER', is_verified=True, is_active=True))
