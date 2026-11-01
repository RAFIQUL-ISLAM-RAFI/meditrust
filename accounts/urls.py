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
