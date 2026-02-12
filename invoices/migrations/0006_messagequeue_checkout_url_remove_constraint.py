from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0005_rename_invoices_in_invoice__f9d171_idx_invoices_in_invoice_a115f4_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='checkout_url',
            field=models.URLField(blank=True, help_text='URL do checkout InfinitePay'),
        ),
        migrations.RemoveConstraint(
            model_name='invoicecontrato',
            name='unique_invoice_contrato_invoice',
        ),
        migrations.CreateModel(
            name='MessageQueue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telefone', models.CharField(blank=True, max_length=20, null=True)),
                ('mensagem', models.TextField()),
                ('tipo', models.CharField(choices=[('5_dias', '5 dias antes'), ('2_dias', '2 dias antes'), ('no_dia', 'No dia'), ('confirmacao', 'Confirmação')], max_length=20)),
                ('agendado_para', models.DateTimeField()),
                ('status', models.CharField(choices=[('pendente', 'Pendente'), ('enviado', 'Enviado'), ('erro', 'Erro')], default='pendente', max_length=20)),
                ('tentativas', models.PositiveSmallIntegerField(default=0)),
                ('enviado_em', models.DateTimeField(blank=True, null=True)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mensagens', to='invoices.invoice')),
            ],
            options={
                'verbose_name': 'Fila de Mensagens',
                'verbose_name_plural': 'Fila de Mensagens',
                'ordering': ['agendado_para'],
                'indexes': [
                    models.Index(fields=['status', 'agendado_para'], name='msgqueue_status_agendado_idx'),
                    models.Index(fields=['invoice'], name='msgqueue_invoice_idx'),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name='messagequeue',
            constraint=models.UniqueConstraint(fields=('invoice', 'tipo'), name='unique_messagequeue_invoice_tipo'),
        ),
    ]
