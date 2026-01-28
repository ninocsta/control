# 💡 SUGESTÕES E ANTI-PATTERNS - Sistema Financeiro

## ✅ PADRÕES IMPLEMENTADOS (BOAS PRÁTICAS)

### 1. **Services Layer**
```python
# ✅ BOM: Lógica isolada em services
from infra.financeiro.services import fechar_periodo
resultado = fechar_periodo(periodo_id, usuario)

# ❌ RUIM: Lógica no model ou view
class PeriodoFinanceiro(models.Model):
    def fechar(self):
        # 200 linhas de código aqui...
```

**Por quê?**
- Testável isoladamente
- Reusável em views, commands, tasks
- Não polui models

---

### 2. **Funções Puras**
```python
# ✅ BOM: Função pura (sem side effects)
def calcular_custo_mensal(cost_object) -> Decimal:
    return (cost_object.valor_total / cost_object.periodo_meses).quantize(Decimal('0.01'))

# ❌ RUIM: Função com side effect
def calcular_custo_mensal(cost_object):
    cost_object.custo_calculado = ...  # Altera estado
    cost_object.save()  # Side effect!
    return cost_object.custo_calculado
```

**Por quê?**
- Previsível (mesmo input = mesmo output)
- Testável (não precisa mockar banco)
- Cacheable

---

### 3. **Transaction Atomic**
```python
# ✅ BOM: Tudo ou nada
with transaction.atomic():
    periodo.fechado = True
    periodo.save()
    for contrato in contratos:
        snapshot = criar_snapshot(contrato)  # Se falhar, rollback automático

# ❌ RUIM: Operações sem transação
periodo.fechado = True
periodo.save()  # Salvou!
for contrato in contratos:
    criar_snapshot(contrato)  # Falhou aqui → período fechado mas sem snapshots!
```

**Por quê?**
- Integridade de dados
- Estado consistente
- Rollback automático

---

### 4. **Select Related / Prefetch Related**
```python
# ✅ BOM: 1 query
contratos = Contrato.objects.select_related('cliente').prefetch_related('dominios')
for c in contratos:
    print(c.cliente.nome)  # Sem query adicional
    print(c.dominios.all())  # Sem query adicional

# ❌ RUIM: N+1 queries
contratos = Contrato.objects.all()
for c in contratos:
    print(c.cliente.nome)  # 1 query por contrato!
    print(c.dominios.all())  # 1 query por contrato!
```

**Por quê?**
- Performance
- Menos carga no banco
- Resposta mais rápida

---

### 5. **Readonly Fields no Admin**
```python
# ✅ BOM: Campos calculados readonly
class ContratoAdmin(admin.ModelAdmin):
    readonly_fields = ('custo_medio', 'margem_media')
    
    def custo_medio(self, obj):
        return f"R$ {obj.snapshots.aggregate(Avg('custo_total'))['custo_total__avg']:.2f}"

# ❌ RUIM: Campo editável que não deve ser
class ContratoAdmin(admin.ModelAdmin):
    fields = ('nome', 'valor_mensal', 'custo_total')  # custo_total deveria ser calculado!
```

**Por quê?**
- Previne edição acidental
- Dados sempre consistentes
- UX clara (cinza = readonly)

---

## 🚫 ANTI-PATTERNS A EVITAR

### 1. **❌ Fat Models (Lógica em Models)**
```python
# ❌ RUIM
class PeriodoFinanceiro(models.Model):
    def fechar(self):
        # 200 linhas de lógica complexa
        contratos = Contrato.objects.filter(...)
        for contrato in contratos:
            # Rateio complexo...
            # Criação de snapshots...
        self.fechado = True
        self.save()

# ✅ BOM: Model enxuto + Service
class PeriodoFinanceiro(models.Model):
    mes = models.IntegerField()
    ano = models.IntegerField()
    fechado = models.BooleanField(default=False)
    # Apenas dados!

# Service separado
def fechar_periodo(periodo_id, usuario):
    # Lógica aqui
```

**Por quê?**
- Model fica focado em representação de dados
- Service fica testável isoladamente
- Mais fácil manter

---

### 2. **❌ Duplicar Snapshots**
```python
# ❌ RUIM: Não verificar se já existe
for contrato in contratos:
    ContratoSnapshot.objects.create(
        contrato=contrato,
        periodo=periodo,
        # ...
    )  # Pode duplicar se rodar 2x!

# ✅ BOM: Constraint único + get_or_create (se fizer sentido)
class ContratoSnapshot(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contrato', 'periodo'],
                name='unique_contrato_snapshot'
            )
        ]

# Ou validar antes
if ContratoSnapshot.objects.filter(contrato=contrato, periodo=periodo).exists():
    raise ValidationError("Snapshot já existe!")
```

**Por quê?**
- Evita dados duplicados
- Integridade no banco
- Erros claros

---

### 3. **❌ Alterar Dados Históricos**
```python
# ❌ RUIM: Permitir edição de snapshot
snapshot = ContratoSnapshot.objects.get(id=123)
snapshot.custo_total = Decimal('999.99')  # Alterando histórico!
snapshot.save()

# ✅ BOM: Proteger com signal
@receiver(pre_save, sender=ContratoSnapshot)
def proteger_snapshot(sender, instance, **kwargs):
    if instance.pk:  # Se já existe
        raise ValidationError("Snapshots são imutáveis!")

# Ou bloquear no admin
class ContratoSnapshotAdmin(admin.ModelAdmin):
    def has_change_permission(self, request, obj=None):
        return False  # Só leitura
```

**Por quê?**
- Histórico imutável
- Auditoria confiável
- Compliance financeiro

---

### 4. **❌ Ignorar Datas de Vigência**
```python
# ❌ RUIM: Buscar todos os contratos
contratos = Contrato.objects.all()  # Inclui contratos encerrados!

# ✅ BOM: Filtrar por período
from django.db.models import Q
contratos_ativos = Contrato.objects.filter(
    data_inicio__lt=ultimo_dia_periodo
).filter(
    Q(data_fim__isnull=True) | Q(data_fim__gte=primeiro_dia_periodo)
)
```

**Por quê?**
- Contratos encerrados não devem entrar no cálculo
- Datas de vigência são críticas
- Evita custos incorretos

---

### 5. **❌ Calcular em Templates**
```python
# ❌ RUIM: Lógica no template
<p>Margem: {{ snapshot.receita|sub:snapshot.custo_total }}</p>

# ✅ BOM: Calcular no backend
class ContratoSnapshot(models.Model):
    margem = models.DecimalField(...)  # Já calculado e salvo

# Ou property
@property
def margem(self):
    return self.receita - self.custo_total
```

**Por quê?**
- Templates devem ser burros (só apresentação)
- Mais fácil testar
- Evita erros de cálculo

---

### 6. **❌ Executar Tarefas Longas Síncronas**
```python
# ❌ RUIM: Fechar período no request
def fechar_periodo_view(request, periodo_id):
    fechar_periodo(periodo_id, request.user.username)  # Pode demorar 30s!
    return redirect('admin:...')  # Cliente esperando...

# ✅ BOM: Usar Celery para operações longas
def fechar_periodo_view(request, periodo_id):
    task_fechar_periodo.delay(periodo_id, request.user.username)
    messages.info(request, "Fechamento iniciado! Será concluído em breve.")
    return redirect('admin:...')
```

**Por quê?**
- Não bloqueia UI
- Retry automático se falhar
- Melhor UX

---

### 7. **❌ Não Usar Celery Beat para Agendamentos**
```python
# ❌ RUIM: Cron separado do Django
# /etc/crontab
0 2 1 * * cd /app && python manage.py fechar_periodo_mes_anterior

# ✅ BOM: Celery Beat (integrado)
app.conf.beat_schedule = {
    'fechar-mes-anterior': {
        'task': 'infra.financeiro.tasks.task_fechar_periodo_mes_anterior',
        'schedule': crontab(day_of_month='1', hour='2', minute='0'),
    },
}
```

**Por quê?**
- Mesmas settings do Django
- Logs centralizados
- Cross-platform
- Configurável via admin (DatabaseScheduler)

---

### 8. **❌ Não Validar Entrada**
```python
# ❌ RUIM: Aceitar qualquer valor
def fechar_periodo(periodo_id, usuario):
    periodo = PeriodoFinanceiro.objects.get(id=periodo_id)
    # Não valida se já está fechado!
    periodo.fechado = True
    periodo.save()

# ✅ BOM: Validar sempre
def fechar_periodo(periodo_id, usuario):
    periodo = PeriodoFinanceiro.objects.get(id=periodo_id)
    if periodo.fechado:
        raise ValidationError(f"Período {periodo} já está fechado!")
    # Continua...
```

**Por quê?**
- Evita estados inconsistentes
- Mensagens de erro claras
- Debugging mais fácil

---

### 9. **❌ Não Usar Signals para Validações**
```python
# ❌ RUIM: Validar manualmente em cada lugar
def alterar_custo(request, cost_id):
    cost = DomainCost.objects.get(id=cost_id)
    # Esqueceu de validar se há snapshot!
    cost.valor_total = request.POST['valor']
    cost.save()

# ✅ BOM: Signal automático
@receiver(pre_save, sender=DomainCost)
def validar_domain_cost(sender, instance, **kwargs):
    validar_custo_com_snapshot(instance, 'DomainCost')
    # Valida automaticamente em QUALQUER save()
```

**Por quê?**
- Validação centralizada
- Impossível esquecer
- Funciona em admin, views, scripts

---

### 10. **❌ Não Usar JSONField para Dados Estruturados**
```python
# ❌ RUIM: Criar tabela para detalhamento
class SnapshotDetalheDominio(models.Model):
    snapshot = models.ForeignKey(ContratoSnapshot)
    dominio_nome = models.CharField(...)
    custo = models.DecimalField(...)
    # Mais queries, mais complexidade

# ✅ BOM: JSONField
class ContratoSnapshot(models.Model):
    detalhamento = models.JSONField(default=dict)
    # {
    #   "dominios": [{"nome": "...", "custo": 123}],
    #   "vps": [...]
    # }
```

**Por quê?**
- Menos queries
- Histórico imutável (JSON não muda)
- Mais flexível
- Fácil exportar

---

## 💡 MELHORIAS FUTURAS

### Curto Prazo (Implementar Já)

#### 1. **Testes Automatizados**
```python
# tests/test_fechamento.py
def test_fechar_periodo_basico():
    periodo = PeriodoFinanceiro.objects.create(mes=1, ano=2026)
    contrato = Contrato.objects.create(...)
    
    resultado = fechar_periodo(periodo.id, 'teste')
    
    assert periodo.fechado == True
    assert ContratoSnapshot.objects.filter(contrato=contrato).count() == 1
```

**Prioridade:** 🔴 ALTA

---

#### 2. **Auditoria com django-simple-history**
```python
# models.py
from simple_history.models import HistoricalRecords

class PeriodoFinanceiro(models.Model):
    # ... campos
    history = HistoricalRecords()

# Uso
periodo.history.all()  # Ver todas as alterações
periodo.history.as_of(datetime(2026, 1, 15))  # Estado em data específica
```

**Prioridade:** 🟡 MÉDIA

---

#### 3. **Cache de Dashboard**
```python
from django.core.cache import cache

@staff_member_required
def dashboard_financeiro(request):
    cache_key = 'dashboard_stats'
    stats = cache.get(cache_key)
    
    if not stats:
        stats = calcular_estatisticas()  # Query pesada
        cache.set(cache_key, stats, 3600)  # 1 hora
    
    return render(request, 'dashboard.html', {'stats': stats})
```

**Prioridade:** 🟡 MÉDIA

---

#### 4. **Notificações por Email**
```python
# tasks.py
@shared_task
def task_alertar_vencimentos(self):
    alertas = coletar_vencimentos()
    
    if alertas:
        send_mail(
            subject='⚠️ Vencimentos Próximos',
            message=formatar_alertas(alertas),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['financeiro@empresa.com'],
        )
```

**Prioridade:** 🟢 BAIXA

---

### Médio Prazo (1-3 meses)

#### 5. **API REST (Django REST Framework)**
```python
# serializers.py
class ContratoSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContratoSnapshot
        fields = '__all__'

# views.py
class ContratoSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ContratoSnapshot.objects.all()
    serializer_class = ContratoSnapshotSerializer
    permission_classes = [IsAuthenticated]
```

**Uso:**
- Integração com Power BI
- App mobile
- Dashboards externos

---

#### 6. **Exportar Relatórios (PDF/Excel)**
```python
from django.http import HttpResponse
import openpyxl

def exportar_periodo_excel(request, periodo_id):
    periodo = PeriodoFinanceiro.objects.get(id=periodo_id)
    snapshots = periodo.contrato_snapshots.all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    
    ws.append(['Contrato', 'Receita', 'Custo', 'Margem'])
    for snap in snapshots:
        ws.append([snap.contrato.nome, snap.receita, snap.custo_total, snap.margem])
    
    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = f'attachment; filename=periodo_{periodo}.xlsx'
    wb.save(response)
    return response
```

---

#### 7. **Gráficos no Dashboard (Chart.js)**
```html
<canvas id="graficoMargem"></canvas>
<script>
const ctx = document.getElementById('graficoMargem');
new Chart(ctx, {
    type: 'line',
    data: {
        labels: {{ periodos|safe }},
        datasets: [{
            label: 'Margem %',
            data: {{ margens|safe }}
        }]
    }
});
</script>
```

---

### Longo Prazo (6+ meses)

#### 8. **Machine Learning - Previsão de Custos**
```python
from sklearn.linear_model import LinearRegression

def prever_custos_proximos_meses(n_meses=3):
    snapshots = ContratoSnapshot.objects.all().order_by('periodo__ano', 'periodo__mes')
    
    X = [[s.periodo.ano, s.periodo.mes] for s in snapshots]
    y = [float(s.custo_total) for s in snapshots]
    
    model = LinearRegression()
    model.fit(X, y)
    
    # Prever próximos meses
    previsoes = []
    for i in range(1, n_meses + 1):
        proximo_mes = date.today() + timedelta(days=30 * i)
        pred = model.predict([[proximo_mes.year, proximo_mes.month]])
        previsoes.append(pred[0])
    
    return previsoes
```

---

#### 9. **Multi-moeda**
```python
class ContratoSnapshot(models.Model):
    moeda = models.CharField(max_length=3, default='BRL')
    taxa_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    
    @property
    def receita_brl(self):
        return self.receita * self.taxa_cambio
```

---

#### 10. **Workflow de Aprovação**
```python
from django_fsm import FSMField, transition

class PeriodoFinanceiro(models.Model):
    status = FSMField(default='aberto')
    
    @transition(field=status, source='aberto', target='em_revisao')
    def enviar_para_revisao(self):
        # Notificar revisor
        pass
    
    @transition(field=status, source='em_revisao', target='aprovado')
    def aprovar(self):
        # Fechar período
        pass
    
    @transition(field=status, source='em_revisao', target='rejeitado')
    def rejeitar(self, motivo):
        # Notificar criador
        pass
```

---

## 🎯 CHECKLIST DE PRODUÇÃO

Antes de fazer deploy em produção, verificar:

### Segurança
- [ ] `DEBUG = False` em produção
- [ ] `SECRET_KEY` seguro e em variável de ambiente
- [ ] `ALLOWED_HOSTS` configurado
- [ ] HTTPS habilitado
- [ ] CSRF_COOKIE_SECURE = True
- [ ] SESSION_COOKIE_SECURE = True
- [ ] Permissões de arquivos corretas
- [ ] Firewall configurado

### Performance
- [ ] Redis configurado para cache
- [ ] Celery Beat rodando
- [ ] Gunicorn ou uWSGI como servidor
- [ ] Nginx como proxy reverso
- [ ] Arquivos estáticos em CDN
- [ ] Database pool configurado

### Monitoramento
- [ ] Sentry para error tracking
- [ ] Logs centralizados (ELK, CloudWatch)
- [ ] Alertas de CPU/memória
- [ ] Backup automatizado diário
- [ ] Health check endpoint

### Testes
- [ ] Cobertura mínima de 80%
- [ ] Testes de integração
- [ ] Testes de carga (locust)
- [ ] Staging environment igual a produção

---

## 🏆 CONCLUSÃO

### O que NÃO fazer:
1. ❌ Lógica em models
2. ❌ Alterar dados históricos
3. ❌ Ignorar datas de vigência
4. ❌ Operações longas síncronas
5. ❌ Não validar entrada
6. ❌ N+1 queries
7. ❌ Não usar transações
8. ❌ Calcular em templates
9. ❌ Duplicar snapshots
10. ❌ Deploy sem testes

### O que fazer:
1. ✅ Services para lógica
2. ✅ Signals para validações
3. ✅ Celery para tarefas longas
4. ✅ transaction.atomic()
5. ✅ select_related / prefetch_related
6. ✅ Testes automatizados
7. ✅ Auditoria de mudanças
8. ✅ Cache inteligente
9. ✅ Monitoramento contínuo
10. ✅ Documentação atualizada

**Sistema está pronto para uso com as devidas precauções!**
