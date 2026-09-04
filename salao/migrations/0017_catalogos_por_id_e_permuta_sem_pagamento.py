from django.db import migrations, models


def limpar_forma_das_permutas(apps, schema_editor):
    """Permuta não tem contrapartida financeira."""
    LancamentoSalao = apps.get_model('salao', 'LancamentoSalao')
    LancamentoSalao.objects.filter(permuta=True).update(forma_pagamento=None)


def restaurar_forma_das_permutas(apps, schema_editor):
    """Restaura o sentinela esperado pela versão anterior da aplicação."""
    FormaPagamentoSalao = apps.get_model('salao', 'FormaPagamentoSalao')
    LancamentoSalao = apps.get_model('salao', 'LancamentoSalao')
    forma_nao_informado = FormaPagamentoSalao.objects.filter(codigo='0').first()
    if forma_nao_informado:
        LancamentoSalao.objects.filter(
            permuta=True,
            forma_pagamento__isnull=True,
        ).update(forma_pagamento=forma_nao_informado)


def _restaurar_codigos(modelo):
    """Gera códigos únicos somente para registros criados após esta migration."""
    existentes = set(
        modelo.objects.exclude(codigo_legado__isnull=True)
        .values_list('codigo_legado', flat=True)
    )
    proximo = 1
    for registro in modelo.objects.filter(codigo_legado__isnull=True).order_by('pk'):
        while True:
            candidato = f'R{proximo:019d}'
            proximo += 1
            if candidato not in existentes:
                break
        registro.codigo_legado = candidato
        registro.save(update_fields=['codigo_legado'])
        existentes.add(candidato)


def restaurar_codigos_produtos(apps, schema_editor):
    _restaurar_codigos(apps.get_model('salao', 'ProdutoSalao'))


def restaurar_codigos_servicos(apps, schema_editor):
    _restaurar_codigos(apps.get_model('salao', 'ServicoSalao'))


class Migration(migrations.Migration):
    dependencies = [('salao', '0016_transacaodivididasalao_and_more')]

    operations = [
        migrations.AlterModelOptions(
            name='produtosalao',
            options={
                'ordering': ['nome'],
                'verbose_name': 'Produto do Salão',
                'verbose_name_plural': 'Produtos do Salão',
            },
        ),
        migrations.RenameField(
            model_name='produtosalao',
            old_name='codigo',
            new_name='codigo_legado',
        ),
        migrations.AlterField(
            model_name='produtosalao',
            name='codigo_legado',
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=20,
                null=True,
                unique=True,
            ),
        ),
        # No rollback, preenche os registros novos antes de tornar o campo
        # obrigatório novamente.
        migrations.RunPython(migrations.RunPython.noop, restaurar_codigos_produtos),
        migrations.AlterModelOptions(
            name='servicosalao',
            options={
                'ordering': ['nome'],
                'verbose_name': 'Serviço do Salão',
                'verbose_name_plural': 'Serviços do Salão',
            },
        ),
        migrations.RenameField(
            model_name='servicosalao',
            old_name='codigo',
            new_name='codigo_legado',
        ),
        migrations.AlterField(
            model_name='servicosalao',
            name='codigo_legado',
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=20,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(migrations.RunPython.noop, restaurar_codigos_servicos),
        migrations.RunPython(limpar_forma_das_permutas, restaurar_forma_das_permutas),
    ]
