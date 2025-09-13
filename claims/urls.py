from django.urls import path
from . import views

app_name = 'claims'

urlpatterns = [
    path('', views.claim_list, name='list'),
    path('search/', views.claim_search, name='search'),              # HTMX partial table update
    path('<int:pk>/', views.claim_detail, name='detail'),
    path('<int:pk>/flag/', views.flag_for_review, name='flag'),      # HTMX action
    path('<int:pk>/add-note/', views.add_note, name='add_note'),     # HTMX action
    path('<int:pk>/report/', views.generate_report, name='report'),  # HTMX action (dummy)
path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('upload-csv/', views.csv_upload, name='csv_upload'),
]
