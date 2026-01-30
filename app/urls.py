from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),
    path('financeiro/', include('infra.financeiro.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include('infra.financeiro.urls')),
]
