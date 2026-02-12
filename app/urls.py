from django.contrib import admin
from django.urls import path, include
from invoices import views as invoice_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('financeiro/', include('infra.financeiro.urls')),
    path('p/<str:ref>/', invoice_views.invoice_checkout_redirect, name='invoice_checkout_redirect'),
    path('webhooks/', include('invoices.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include(('infra.financeiro.urls', 'financeiro'), namespace='financeiro_root')),
]
