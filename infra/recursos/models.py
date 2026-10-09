"""
Infra unificada: tudo que tem fornecedor, custo e/ou data de renovação (domínio, VPS,
hosting, backup, e-mail, certificado, licença...). Substitui os apps dominios/hosting/vps/
backups/emails (dados copiados na migração 0002; tabelas antigas ficam só como legado).
"""
from django.db import models
from django.db.models import Q

from contratos.models import Contrato
from infra.core.models import InfraCostModel


class Recurso(models.Model):
    TIPO_CHOICES = [
        ('dominio', 'Domínio'),
        ('vps', 'VPS'),
        ('hosting', 'Hosting'),
        ('backup', 'Backup'),
        ('email', 'E-mail'),
        ('outro', 'Outro'),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    nome = models.CharField(max_length=200)
    fornecedor = models.CharField(max_length=200, blank=True)
    detalhe = models.CharField(max_length=200, blank=True, help_text='Ex: plano, nº de caixas, servidor')
    pai = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='filhos',
        help_text='Backup de uma VPS, e-mail de um domínio... Sem contratos próprios, o custo segue os do pai.',
    )
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tipo', 'nome']

    def __str__(self):
        return f"{self.get_tipo_display()} {self.nome}"

    def custo_atual(self):
        return self.custos.filter(ativo=True).order_by('-data_inicio').first()

    def vinculos_em(self, primeiro_dia, proximo_mes):
        """Vínculos com contrato no período; sem vínculo próprio usa os do pai."""
        filtro = Q(data_inicio__lt=proximo_mes) & (Q(data_fim__isnull=True) | Q(data_fim__gte=primeiro_dia))
        proprios = self.vinculos.filter(filtro)
        if not self.vinculos.exists() and self.pai_id:
            return self.pai.vinculos.filter(filtro)
        return proprios


class RecursoContrato(models.Model):
    """Recurso usado por um contrato num intervalo. Custo do mês é dividido igualmente entre os vínculos ativos."""
    recurso = models.ForeignKey(Recurso, on_delete=models.CASCADE, related_name='vinculos')
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='vinculos_recurso')
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-data_inicio']

    def __str__(self):
        return f"{self.recurso} → {self.contrato}"


class CustoRecurso(InfraCostModel):
    """Histórico de custo/renovação. Mudou o preço? Encerra este (data_fim) e cria outro."""
    recurso = models.ForeignKey(Recurso, on_delete=models.PROTECT, related_name='custos')

    class Meta:
        ordering = ['-data_inicio']

    def __str__(self):
        return f"{self.recurso} R$ {self.valor_total}/{self.periodo_meses}m"
