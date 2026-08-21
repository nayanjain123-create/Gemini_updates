from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

from accounts import views as accounts_views

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    return redirect('accounts:login')

handler403 = 'accounts.views.custom_403_view'
handler404 = 'accounts.views.custom_404_view'
handler500 = 'accounts.views.custom_500_view'

urlpatterns = [
    path('ping/', accounts_views.ping_view, name='root_ping'),
    path('', root_redirect, name='root'),
    path('admin/', admin.site.urls),
    path('', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('', include(('reports.urls', 'reports'), namespace='reports')),
    path('', include(('compliance.urls', 'compliance'), namespace='compliance')),
    path('', include(('audit.urls', 'audit'), namespace='audit')),
]
