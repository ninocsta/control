import unicodedata

from django.db import migrations


# Nomes que, por padrão, não têm contrapartida no extrato da adquirente.
FORA_DO_EXTRATO = {'dinheiro', 'especie', 'nao informado'}


def _normalizar(valor):
    texto = unicodedata.normalize('NFKD', (valor or '').strip().lower())
    return ''.join(ch for ch in texto if not unicodedata.combining(ch))


def marcar_formas_fora_do_extrato(apps, schema_editor):
    FormaPagamentoSalao = apps.get_model('salao', 'FormaPagamentoSalao')
    for forma in FormaPagamentoSalao.objects.all():
        if _normalizar(forma.nome) in FORA_DO_EXTRATO:
            forma.concilia_extrato = False
            forma.save(update_fields=['concilia_extrato'])


def reverter(apps, schema_editor):
    apps.get_model('salao', 'FormaPagamentoSalao').objects.update(concilia_extrato=True)


class Migration(migrations.Migration):
    dependencies = [('salao', '0014_formapagamentosalao_concilia_extrato')]
    operations = [migrations.RunPython(marcar_formas_fora_do_extrato, reverter)]
