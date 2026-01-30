from django.urls import path
from . import views

app_name = 'financeiro'

urlpatterns = [
    path('', views.dashboard_financeiro, name='dashboard_default'),
    path('dashboard/', views.dashboard_financeiro, name='dashboard'),
]
