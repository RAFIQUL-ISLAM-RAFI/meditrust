from django import forms
from django.utils import timezone
from .models import Batch, Medicine
from .utils import normalize_base_url


class MedicineForm(forms.ModelForm):
    class Meta:
        model = Medicine
        fields = ['name', 'generic_name', 'composition', 'description', 'side_effects', 'precautions', 'dosage_info']


class BatchForm(forms.Form):
    medicine = forms.ModelChoiceField(queryset=Medicine.objects.none())
    batch_number = forms.CharField(max_length=50)
    total_quantity = forms.IntegerField(min_value=1, max_value=5000, label='Quantity (strips)')
    tablets_per_unit = forms.IntegerField(min_value=1, max_value=100, initial=10, label='Tablets per strip')
    manufacture_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    expiry_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medicine'].queryset = Medicine.objects.filter(manufacturer=user)

    def clean(self):
        data = super().clean()
        today = timezone.localdate()
        made, expiry = data.get('manufacture_date'), data.get('expiry_date')
        if made and made > today:
            self.add_error('manufacture_date', 'Manufacture date cannot be in the future.')
        if expiry and expiry < today:
            self.add_error('expiry_date', 'Expiry date cannot be in the past.')
        if made and expiry and expiry <= made:
            self.add_error('expiry_date', 'Expiry date must be after manufacture date.')
        if data.get('medicine') and data.get('batch_number') and Batch.objects.filter(
                medicine=data['medicine'], batch_number__iexact=data['batch_number']).exists():
            self.add_error('batch_number', 'This medicine already has a batch with that number.')
        return data


class RecallForm(forms.Form):
    recall_reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}), label='Recall reason')


class QRAddressForm(forms.Form):
    base_url = forms.CharField(max_length=250, label='Website address printed in QR codes')

    def clean_base_url(self):
        try:
            return normalize_base_url(self.cleaned_data['base_url'])
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
