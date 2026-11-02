from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from accounts.urls import urlpatterns as account_urls
from medicines.urls import urlpatterns as medicine_urls
from tracking.urls import urlpatterns as tracking_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', RedirectView.as_view(url='/login/', query_string=True)),
    path('', include((account_urls + medicine_urls + tracking_urls, 'ui'), namespace='ui')),
]
