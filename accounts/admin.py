from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm
from .models import User


class AccountCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role', 'organization_name', 'license_no', 'address', 'is_verified')


@admin.register(User)
class AccountAdmin(UserAdmin):
    add_form = AccountCreationForm
    fieldsets = UserAdmin.fieldsets + (('MediTrust organisation', {'fields': ('role', 'organization_name', 'license_no', 'address', 'is_verified')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('MediTrust organisation', {'fields': ('email', 'role', 'organization_name', 'license_no', 'address', 'is_verified')}),)
    list_display = ('username', 'organization_name', 'role', 'license_no', 'is_verified', 'is_active')
    list_filter = UserAdmin.list_filter + ('role', 'is_verified')
    actions = ['approve_organisations']

    @admin.action(description='Approve selected organisations after checking their licences')
    def approve_organisations(self, request, queryset):
        self.message_user(request, f"Approved {queryset.exclude(role='ADMIN').update(is_verified=True)} organisations.")


admin.site.site_header = 'MediTrust administration'
admin.site.site_title = 'MediTrust'
