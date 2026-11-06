from django.urls import path
from . import views

urlpatterns = [
    path('scan/', views.scan, name='scan'),
    path('check/', views.scan, name='check_serial'),
    path('verify/<str:code>/', views.verify, name='verify'),
    path('api/verify/<str:code>/', views.api_verify, name='api_verify'),
    path('batch/<int:pk>/transfer/', views.transfer_batch, name='transfer_batch'),
    path('pharmacy/', views.pharmacy, name='pharmacy'),
    path('pharmacy/receive/', views.receive_scan, name='receive'),
    path('receive/<str:code>/', views.receive_confirm, name='receive_confirm'),
    path('pharmacy/receive/<str:code>/', views.receive_confirm, name='receive_legacy'),
    path('pharmacy/sales/', views.sales, name='sales'),
    path('sell/<str:code>/', views.sell, name='sell'),
]
