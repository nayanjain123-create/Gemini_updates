from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        try:
            from .keep_alive import start_keep_alive_thread
            start_keep_alive_thread()
        except Exception:
            pass
