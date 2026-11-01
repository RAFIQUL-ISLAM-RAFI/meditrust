from django.urls import path
from . import views

urlpatterns = [
    path('manufacturer/', views.manufacturer, name='manufacturer'),
    path('manufacturer/medicine/new/', views.medicine_new, name='medicine_new'),
    path('manufacturer/batch/new/', views.create_batch, name='create_batch'),
    path('manufacturer/qr/<int:pk>/', views.qr_sheet, name='qr_sheet'),
    path('batch/<int:pk>/recall/', views.recall_batch, name='recall_batch'),
    path('qr/unit/<str:code>.png', views.unit_qr, name='unit_qr'),
    path('qr/batch/<str:code>.png', views.batch_qr, name='batch_qr'),
]
