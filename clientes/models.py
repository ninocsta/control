from django.db import models

# Create your models here.


class Cliente(models.Model):
    TIPO_CHOICES = [
        ('pessoa_fisica', 'Pessoa Física'),
        ('pessoa_juridica', 'Pessoa Jurídica'),
        ('interno', 'Interno'),
    ]

    nome = models.CharField(max_length=100)
    email = models.EmailField(unique=True, null=True, blank=True)
    telefone = models.CharField(max_length=15, blank=True, null=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)


    data_criacao = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nome']

    def __str__(self):
        return self.nome