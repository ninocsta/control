from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0003_invoicecontrato'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='invoicecontrato',
            constraint=models.UniqueConstraint(fields=('invoice',), name='unique_invoice_contrato_invoice'),
        ),
    ]
