from django.urls import path
from .views import *

app_name = 'panel'

urlpatterns = [
    # Authentication
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # Panel
    path('', ServerListView.as_view(), name='server_list'),
    path('servers/create/', ServerCreateView.as_view(), name='server_create'),
    path('servers/<int:pk>/', ServerDetailView.as_view(), name='server_detail'),
    path('servers/<int:pk>/logs/', ServerLogListView.as_view(), name='server_logs'),
    path('servers/<int:server_id>/settings/', ServerSettingsView.as_view(), name='server_settings'),
    path('servers/<int:server_id>/plugins/', PluginListView.as_view(), name='plugins'),
    path('servers/<int:server_id>/plugins/add/', PluginAddView.as_view(), name='plugin_add'),
    path('servers/<int:server_id>/backups/', BackupListView.as_view(), name='backups'),
    path('servers/<int:server_id>/resources/', ResourceUsageListView.as_view(), name='resource_usage'),
    
    # Profile
    path('profile/', UserProfileView.as_view(), name='user_profile'),
]
