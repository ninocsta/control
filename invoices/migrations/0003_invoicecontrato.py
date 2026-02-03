from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal
from django.core.validators import MinValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0002_alter_invoice_options_and_more'),
        ('contratos', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InvoiceContrato',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valor', models.DecimalField(decimal_places=2, max_digits=10, validators=[MinValueValidator(Decimal('0.00'))])),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('contrato', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='itens_invoice', to='contratos.contrato')),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='itens_contrato', to='invoices.invoice')),
            ],
            options={
                'verbose_name': 'Invoice x Contrato',
                'verbose_name_plural': 'Invoices x Contratos',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.AddConstraint(
            model_name='invoicecontrato',
            constraint=models.UniqueConstraint(fields=('invoice', 'contrato'), name='unique_invoice_contrato'),
        ),
        migrations.AddIndex(
            model_name='invoicecontrato',
            index=models.Index(fields=['invoice'], name='invoices_in_invoice__f9d171_idx'),
        ),
        migrations.AddIndex(
            model_name='invoicecontrato',
            index=models.Index(fields=['contrato'], name='invoices_in_contrato_1495d0_idx'),
        ),
    ]
