from django.contrib import admin
from config.admin_utils import ReadOnlyAdmin
from .models import OwnershipTransfer, Sale, VerificationLog


@admin.register(VerificationLog)
class LogAdmin(ReadOnlyAdmin):
    list_display = ('scanned_at', 'unit', 'verification_result', 'is_suspicious', 'location')
    list_filter = ('verification_result', 'is_suspicious')


admin.site.register(OwnershipTransfer, ReadOnlyAdmin)
admin.site.register(Sale, ReadOnlyAdmin)
