from django.urls import path
from . import views

urlpatterns = [
    path('compliance/', views.compliance_report_view, name='compliance_index'),
    path('compliance-report/', views.compliance_report_view, name='compliance_report'),
    path('compliance-report/<int:year>/<int:month>/', views.compliance_report_view, name='compliance_report_by_month'),
    path('compliance-report/<int:year>/<int:month>/export/csv/', views.compliance_export_csv_view, name='compliance_export_csv'),
    path('compliance-report/<int:year>/<int:month>/export/excel/', views.compliance_export_excel_view, name='compliance_export_excel'),
    path('compliance-report/<int:year>/<int:month>/print/', views.compliance_print_view, name='compliance_print'),
    path('compliance/<int:item_id>/', views.compliance_detail_api, name='compliance_detail_api'),
    path('compliance/<int:item_id>/mark-done/', views.compliance_mark_done_view, name='compliance_mark_done'),
    path('compliance/<int:item_id>/mark-na/', views.compliance_mark_na_view, name='compliance_mark_na'),
    path('compliance/<int:item_id>/comment/', views.compliance_comment_add_view, name='compliance_comment_add'),
]
