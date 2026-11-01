from django.contrib import admin
from config.admin_utils import ReadOnlyAdmin
from .models import Batch, Medicine, MedicineUnit


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'generic_name', 'manufacturer')
    search_fields = ('name', 'generic_name')

    def get_readonly_fields(self, request, obj=None):
        # Changing issued metadata requires a deliberate reissue workflow, not silent re-signing.
        return [f.name for f in self.model._meta.fields] if obj and obj.batches.exists() else []


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('batch_number', 'medicine', 'expiry_date', 'is_recalled')
    list_filter = ('is_recalled',)
    readonly_fields = ('integrity_signature', 'is_recalled', 'recall_reason', 'recalled_at', 'recalled_by')

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields] if obj else self.readonly_fields


@admin.register(MedicineUnit)
class UnitAdmin(ReadOnlyAdmin):
    list_display = ('serial_number', 'batch', 'current_owner', 'sold_pills', 'total_pills', 'duplicate_detected')
    search_fields = ('serial_number', 'batch__batch_number')
    list_filter = ('duplicate_detected',)
