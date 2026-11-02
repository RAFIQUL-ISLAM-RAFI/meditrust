from django.urls import path
from . import views

app_name = 'ui'
urlpatterns = [
    path('', views.home, name='landing'),
    path('scan/', views.scan, name='scan'),
    path('check/', views.scan, name='check_serial'),
    path('verify/<str:code>/', views.verify, name='verify'),
    path('api/verify/<str:code>/', views.api_verify, name='api_verify'),
    path('login/', views.login_view, name='login'),
    path('login/manufacturer/', views.login_view, {'portal': 'manufacturer'}, name='manufacturer_login'),
    path('login/pharmacy/', views.login_view, {'portal': 'pharmacy'}, name='retailer_login'),
    path('login/admin/', views.login_view, {'portal': 'admin'}, name='admin_login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('manufacturer/', views.manufacturer, name='manufacturer'),
    path('manufacturer/medicine/new/', views.medicine_new, name='medicine_new'),
    path('manufacturer/batch/new/', views.create_batch, name='create_batch'),
    path('manufacturer/qr/<int:pk>/', views.qr_sheet, name='qr_sheet'),
    path('batch/<int:pk>/transfer/', views.transfer_batch, name='transfer_batch'),
    path('batch/<int:pk>/recall/', views.recall_batch, name='recall_batch'),
    path('pharmacy/', views.pharmacy, name='pharmacy'),
    path('pharmacy/receive/', views.receive_scan, name='receive'),
    path('receive/<str:code>/', views.receive_confirm, name='receive_confirm'),
    path('pharmacy/receive/<str:code>/', views.receive_confirm, name='receive_legacy'),
    path('pharmacy/sales/', views.sales, name='sales'),
    path('sell/<str:code>/', views.sell, name='sell'),
    path('qr/unit/<str:code>.png', views.unit_qr, name='unit_qr'),
    path('qr/batch/<str:code>.png', views.batch_qr, name='batch_qr'),
]
