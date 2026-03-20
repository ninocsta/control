from django.urls import path

from . import views

app_name = 'salao'

urlpatterns = [
    path('', views.index, name='index'),
    path('lancamentos/', views.lancamentos, name='lancamentos'),
    path('despesas/', views.despesas, name='despesas'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('servicos/', views.servicos, name='servicos'),
    path('categorias/', views.categorias, name='categorias'),
    path('pagamentos/', views.pagamentos, name='pagamentos'),
]
