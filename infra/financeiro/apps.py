from django.apps import AppConfig


class FinanceiroConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'infra.financeiro'
    
    def ready(self):
        """Importar signals quando o app estiver pronto."""
        import infra.financeiro.signals
