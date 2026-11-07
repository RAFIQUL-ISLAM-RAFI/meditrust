"""URL routes for the accounts app.

All three portal-specific login routes (manufacturer / pharmacy / admin)
reuse the single ``login_view`` — the ``{'portal': ...}`` dict is
forwarded to the view, which enforces the expected role inside
``RoleAuthenticationForm``. Keeping one view avoids duplicating the
login logic for each role.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='landing'),
    path('login/', views.login_view, name='login'),
    path('login/manufacturer/', views.login_view, {'portal': 'manufacturer'}, name='manufacturer_login'),
    path('login/pharmacy/', views.login_view, {'portal': 'pharmacy'}, name='retailer_login'),
    path('login/admin/', views.login_view, {'portal': 'admin'}, name='admin_login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
]
