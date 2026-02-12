from django.urls import path

from . import views

app_name = 'invoices'

urlpatterns = [
    path('infinitepay/', views.infinitepay_webhook, name='infinitepay_webhook'),
]
