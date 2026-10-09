from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'painel'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('login/', auth_views.LoginView.as_view(template_name='painel/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('cobrancas/', views.cobrancas, name='cobrancas'),
    path('cobrancas/gerar/', views.gerar_mensalidades, name='gerar_mensalidades'),
    path('cobrancas/avulsa/', views.avulsa_nova, name='avulsa_nova'),
    path('faturas/<int:pk>/', views.fatura, name='fatura'),
    path('faturas/<int:pk>/<str:acao>/', views.fatura_acao, name='fatura_acao'),

    path('clientes/', views.clientes, name='clientes'),
    path('clientes/novo/', views.cliente_form, name='cliente_novo'),
    path('clientes/<int:pk>/', views.cliente, name='cliente'),
    path('clientes/<int:pk>/editar/', views.cliente_form, name='cliente_editar'),

    path('contratos/novo/', views.contrato_form, name='contrato_novo'),
    path('contratos/<int:pk>/editar/', views.contrato_form, name='contrato_editar'),
    path('contratos/<int:pk>/reajuste/', views.contrato_reajuste, name='contrato_reajuste'),
    path('contratos/<int:pk>/encerrar/', views.contrato_encerrar, name='contrato_encerrar'),
    path('reajustes/<int:pk>/excluir/', views.reajuste_excluir, name='reajuste_excluir'),

    path('agenda/', views.agenda, name='agenda'),

    path('recursos/', views.recursos, name='recursos'),
    path('recursos/novo/', views.recurso_form, name='recurso_novo'),
    path('recursos/<int:pk>/', views.recurso, name='recurso'),
    path('recursos/<int:pk>/editar/', views.recurso_form, name='recurso_editar'),
    path('custos/<int:pk>/editar/', views.custo_editar, name='custo_editar'),
    path('custos/<int:pk>/renovar/', views.custo_renovar, name='custo_renovar'),
    path('vinculos/<int:pk>/encerrar/', views.vinculo_encerrar, name='vinculo_encerrar'),

    path('financeiro/', views.financeiro, name='financeiro'),
    path('financeiro/<int:ano>/<int:mes>/', views.periodo, name='periodo'),
    path('financeiro/<int:ano>/<int:mes>/fechar/', views.periodo_fechar, name='periodo_fechar'),
]
