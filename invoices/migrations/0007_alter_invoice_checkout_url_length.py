from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0006_messagequeue_checkout_url_remove_constraint'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='checkout_url',
            field=models.URLField(max_length=500, blank=True, help_text='URL do checkout InfinitePay'),
        ),
    ]
