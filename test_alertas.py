#!/usr/bin/env python
"""
Script para testar o sistema de alertas de vencimento.

Uso:
    python test_alertas.py
"""
import os
import sys
import django
from datetime import date, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from infra.financeiro.tasks import task_alertar_vencimentos
from infra.dominios.models import DomainCost
from infra.vps.models import VPSCost
from infra.emails.models import DomainEmailCost
from infra.hosting.models import HostingCost
from infra.backups.models import VPSBackupCost


def verificar_custos_ativos():
    """Verifica quantos custos ativos existem no sistema."""
    print("\n" + "="*60)
    print("🔍 VERIFICAÇÃO DE CUSTOS ATIVOS")
    print("="*60)
    
    hoje = date.today()
    datas_alerta = [
        hoje,
        hoje + timedelta(days=7),
        hoje + timedelta(days=30)
    ]
    
    print(f"\n📅 Data de hoje: {hoje.strftime('%d/%m/%Y')}")
    print(f"📅 Datas monitoradas:")
    for d in datas_alerta:
        print(f"   - {d.strftime('%d/%m/%Y')} ({(d - hoje).days} dias)")
    
    # Domínios
    dominios = DomainCost.objects.filter(ativo=True)
    dominios_vencendo = dominios.filter(vencimento__in=datas_alerta)
    print(f"\n🌐 Domínios:")
    print(f"   Total ativos: {dominios.count()}")
    print(f"   Vencendo: {dominios_vencendo.count()}")
    for cost in dominios_vencendo:
        dias = (cost.vencimento - hoje).days
        print(f"      • {cost.domain.nome} - Vence em {dias} dias ({cost.vencimento.strftime('%d/%m/%Y')}) - R$ {cost.valor_total}")
    
    # VPS
    vps = VPSCost.objects.filter(ativo=True)
    vps_vencendo = vps.filter(vencimento__in=datas_alerta)
    print(f"\n💻 VPS:")
    print(f"   Total ativos: {vps.count()}")
    print(f"   Vencendo: {vps_vencendo.count()}")
    for cost in vps_vencendo:
        dias = (cost.vencimento - hoje).days
        print(f"      • {cost.vps.nome} - Vence em {dias} dias ({cost.vencimento.strftime('%d/%m/%Y')}) - R$ {cost.valor_total}")
    
    # Emails
    emails = DomainEmailCost.objects.filter(ativo=True)
    emails_vencendo = emails.filter(vencimento__in=datas_alerta)
    print(f"\n📧 Emails:")
    print(f"   Total ativos: {emails.count()}")
    print(f"   Vencendo: {emails_vencendo.count()}")
    for cost in emails_vencendo:
        dias = (cost.vencimento - hoje).days
        print(f"      • {cost.email.dominio.nome} - Vence em {dias} dias ({cost.vencimento.strftime('%d/%m/%Y')}) - R$ {cost.valor_total}")
    
    # Hosting
    hostings = HostingCost.objects.filter(ativo=True)
    hostings_vencendo = hostings.filter(vencimento__in=datas_alerta)
    print(f"\n🌐 Hostings:")
    print(f"   Total ativos: {hostings.count()}")
    print(f"   Vencendo: {hostings_vencendo.count()}")
    for cost in hostings_vencendo:
        dias = (cost.vencimento - hoje).days
        print(f"      • {cost.hosting.nome} - Vence em {dias} dias ({cost.vencimento.strftime('%d/%m/%Y')}) - R$ {cost.valor_total}")
    
    # Backups
    backups = VPSBackupCost.objects.filter(ativo=True)
    backups_vencendo = backups.filter(vencimento__in=datas_alerta)
    print(f"\n💾 Backups VPS:")
    print(f"   Total ativos: {backups.count()}")
    print(f"   Vencendo: {backups_vencendo.count()}")
    for cost in backups_vencendo:
        dias = (cost.vencimento - hoje).days
        print(f"      • {cost.backup.nome} ({cost.backup.vps.nome}) - Vence em {dias} dias ({cost.vencimento.strftime('%d/%m/%Y')}) - R$ {cost.valor_total}")
    
    total_vencendo = (
        dominios_vencendo.count() + 
        vps_vencendo.count() + 
        emails_vencendo.count() + 
        hostings_vencendo.count() + 
        backups_vencendo.count()
    )
    
    print(f"\n{'='*60}")
    print(f"📊 TOTAL DE VENCIMENTOS: {total_vencendo}")
    print(f"{'='*60}\n")
    
    return total_vencendo


def testar_task():
    """Executa a task de alertas e mostra o resultado."""
    print("\n" + "="*60)
    print("🚀 EXECUTANDO TASK DE ALERTAS")
    print("="*60 + "\n")
    
    try:
        resultado = task_alertar_vencimentos()
        
        print(f"\n✅ Task executada com sucesso!")
        print(f"\n📋 Resultado:")
        print(f"   Total de alertas: {resultado['total_alertas']}")
        
        if resultado['alertas']:
            print(f"\n📧 Alertas que serão enviados por email:")
            for alerta in resultado['alertas']:
                print(f"\n   • {alerta['tipo']}: {alerta['nome']}")
                print(f"     Vencimento: {alerta['vencimento']}")
                print(f"     Dias restantes: {alerta['dias_restantes']}")
                print(f"     Valor: R$ {alerta['valor']:.2f}")
                if 'fornecedor' in alerta:
                    print(f"     Fornecedor: {alerta['fornecedor']}")
        else:
            print(f"\n   ℹ️ Nenhum vencimento encontrado nos próximos 30 dias.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erro ao executar task:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Executa o teste completo."""
    print("\n" + "="*60)
    print("🧪 TESTE DO SISTEMA DE ALERTAS DE VENCIMENTO")
    print("="*60)
    
    # 1. Verificar custos
    total_vencimentos = verificar_custos_ativos()
    
    # 2. Executar task
    sucesso = testar_task()
    
    # 3. Resumo
    print("\n" + "="*60)
    print("📊 RESUMO DO TESTE")
    print("="*60)
    
    if total_vencimentos == 0:
        print("\n⚠️ ATENÇÃO: Não há vencimentos nos próximos 30 dias.")
        print("   Para testar o envio de email, cadastre custos com vencimento:")
        print("   - Hoje")
        print("   - Daqui a 7 dias")
        print("   - Daqui a 30 dias")
    else:
        print(f"\n✅ {total_vencimentos} vencimento(s) encontrado(s).")
    
    if sucesso:
        print("\n✅ Task executada com sucesso!")
        if total_vencimentos > 0:
            print("\n📧 Email enviado para: nicolaskcdev@gmail.com")
            print("   Verifique sua caixa de entrada.")
    else:
        print("\n❌ Erro ao executar task.")
        print("   Verifique os logs acima.")
    
    print("\n" + "="*60 + "\n")


if __name__ == '__main__':
    main()
