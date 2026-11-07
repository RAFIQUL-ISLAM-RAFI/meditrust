"""Forms used by the accounts app.

* ``RoleAuthenticationForm`` — login form that enforces the role expected
  by the portal being used (manufacturer / pharmacy / admin), preventing
  a user from logging into the wrong portal.
* ``RegisterForm`` — public self-registration form; new accounts are
  created unverified and must be approved by an administrator.
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import User


class RoleAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, expected_role=None, **kwargs):
        self.expected_role = expected_role
        super().__init__(*args, **kwargs)

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if self.expected_role and user.role != self.expected_role:
            raise forms.ValidationError('This account belongs to a different portal. Choose the matching login below.')


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['role', 'organization_name', 'license_no', 'address', 'email', 'username', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [(User.Role.MANUFACTURER, 'Manufacturer'), (User.Role.RETAILER, 'Pharmacy / retailer')]
        for key in ['organization_name', 'license_no', 'address', 'email']:
            self.fields[key].required = True
