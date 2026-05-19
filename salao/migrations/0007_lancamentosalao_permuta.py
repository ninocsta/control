from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salao', '0006_compraestoquesalao_custos_adicionais'),
    ]

    operations = [
        migrations.AddField(
            model_name='lancamentosalao',
            name='permuta',
            field=models.BooleanField(default=False),
        ),
    ]

