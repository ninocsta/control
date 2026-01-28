from django.urls import path
from . import views

app_name = 'financeiro'

urlpatterns = [
    path('dashboard/', views.dashboard_financeiro, name='dashboard'),
]
