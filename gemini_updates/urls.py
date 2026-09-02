from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.views.generic.base import RedirectView

from accounts import views as accounts_views

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    return redirect('accounts:login')

handler403 = 'accounts.views.custom_403_view'
handler404 = 'accounts.views.custom_404_view'
handler500 = 'accounts.views.custom_500_view'

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
    path('ping/', accounts_views.ping_view, name='root_ping'),
    path('manifest.webmanifest', accounts_views.manifest_view, name='pwa_manifest'),
    path('service-worker.js', accounts_views.service_worker_view, name='pwa_service_worker'),
    path('offline/', accounts_views.offline_view, name='pwa_offline'),
    path('', root_redirect, name='root'),
    path('admin/', admin.site.urls),
    path('', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('', include(('reports.urls', 'reports'), namespace='reports')),
    path('', include(('compliance.urls', 'compliance'), namespace='compliance')),
    path('', include(('audit.urls', 'audit'), namespace='audit')),
]
