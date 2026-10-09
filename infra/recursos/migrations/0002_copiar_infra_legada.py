"""Copia domínios, hostings, VPS, backups e e-mails (apps legados) para Recurso/CustoRecurso.

Vínculos sem data (M2M de domínio/hosting, FK de e-mail) herdam as datas do contrato,
que era o critério do rateio antigo. As tabelas antigas não são tocadas.
"""
from django.db import migrations

CAMPOS_CUSTO = ('valor_total', 'periodo_meses', 'data_inicio', 'data_fim', 'vencimento', 'pago_pelo_cliente', 'ativo')


def copiar(apps, schema_editor):
    Recurso = apps.get_model('recursos', 'Recurso')
    RecursoContrato = apps.get_model('recursos', 'RecursoContrato')
    CustoRecurso = apps.get_model('recursos', 'CustoRecurso')
    Dominio = apps.get_model('dominios', 'Dominio')
    Hosting = apps.get_model('hosting', 'Hosting')
    VPS = apps.get_model('vps', 'VPS')
    VPSContrato = apps.get_model('vps', 'VPSContrato')
    VPSBackup = apps.get_model('backups', 'VPSBackup')
    DomainEmail = apps.get_model('emails', 'DomainEmail')

    if Recurso.objects.exists():
        return

    def custos(recurso, qs):
        for c in qs:
            CustoRecurso.objects.create(recurso=recurso, **{f: getattr(c, f) for f in CAMPOS_CUSTO})

    def vincular_pelas_datas_do_contrato(recurso, contratos):
        for contrato in contratos:
            RecursoContrato.objects.create(
                recurso=recurso, contrato=contrato, data_inicio=contrato.data_inicio, data_fim=contrato.data_fim,
            )

    por_dominio = {}
    for d in Dominio.objects.all():
        r = Recurso.objects.create(tipo='dominio', nome=d.nome, fornecedor=d.fornecedor, ativo=d.ativo)
        por_dominio[d.pk] = r
        vincular_pelas_datas_do_contrato(r, d.contratos.all())
        custos(r, d.costs.all())

    for h in Hosting.objects.all():
        r = Recurso.objects.create(tipo='hosting', nome=h.nome, fornecedor=h.fornecedor, ativo=h.ativo)
        vincular_pelas_datas_do_contrato(r, h.contratos.all())
        custos(r, h.costs.all())

    por_vps = {}
    for v in VPS.objects.all():
        r = Recurso.objects.create(tipo='vps', nome=v.nome, fornecedor=v.fornecedor, ativo=v.ativo)
        por_vps[v.pk] = r
        for link in VPSContrato.objects.filter(vps=v):
            RecursoContrato.objects.create(
                recurso=r, contrato_id=link.contrato_id, data_inicio=link.data_inicio, data_fim=link.data_fim,
            )
        custos(r, v.costs.all())

    for b in VPSBackup.objects.all():
        r = Recurso.objects.create(
            tipo='backup', nome=b.nome, fornecedor=b.fornecedor or VPS.objects.get(pk=b.vps_id).fornecedor,
            ativo=b.ativo, pai=por_vps[b.vps_id],
        )
        custos(r, b.costs.all())

    for e in DomainEmail.objects.all():
        dominio = por_dominio[e.dominio_id]
        r = Recurso.objects.create(
            tipo='email', nome=dominio.nome, fornecedor=e.fornecedor, ativo=e.ativo, pai=dominio,
            detalhe=f'{e.quantidade_caixas} caixa(s)',
        )
        vincular_pelas_datas_do_contrato(r, [e.contrato])
        custos(r, e.costs.all())


class Migration(migrations.Migration):

    dependencies = [
        ('recursos', '0001_initial'),
        ('dominios', '0002_domaincost_pago_pelo_cliente_and_more'),
        ('hosting', '0002_hostingcost_pago_pelo_cliente_and_more'),
        ('vps', '0002_vpscost_pago_pelo_cliente_alter_vpscost_vencimento'),
        ('backups', '0002_vpsbackupcost_pago_pelo_cliente_and_more'),
        ('emails', '0002_domainemailcost_pago_pelo_cliente_and_more'),
    ]

    operations = [
        migrations.RunPython(copiar, migrations.RunPython.noop),
    ]
