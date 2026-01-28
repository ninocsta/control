# infra/emails/models.py
from django.db import models
from infra.core import models as core_models
from infra.dominios.models import Dominio


class DomainEmail(models.Model):
    """
    Serviço de e-mail vinculado a um domínio específico.
    Ex: email@cliente.com
    """

    dominio = models.ForeignKey(
        Dominio,
        on_delete=models.CASCADE,
        related_name='emails'
    )

    fornecedor = models.CharField(
        max_length=200,
        help_text="Ex: Hostinger, Google, Zoho"
    )

    quantidade_caixas = models.PositiveIntegerField(default=1)

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email {self.dominio.nome_dominio}"
    
class DomainEmailCost(core_models.InfraCostModel):
    """
    Histórico de custos do e-mail do domínio.
    Permite:
    - período gratuito (valor_total = 0)
    - troca de preço futura
    """

    email = models.ForeignKey(
        DomainEmail,
        on_delete=models.PROTECT,
        related_name='costs'
    )

    class Meta:
        ordering = ['-data_inicio']

