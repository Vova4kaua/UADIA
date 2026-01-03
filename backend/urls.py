from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'servers', ServerViewSet, basename='server')
router.register(r'profiles', UserProfileViewSet, basename='profile')
router.register(r'server-logs', ServerLogViewSet, basename='serverlog')
router.register(r'settings', ServerSettingsViewSet, basename='settings')
router.register(r'plugins', PluginViewSet, basename='plugin')
router.register(r'backups', BackupViewSet, basename='backup')
router.register(r'resource-usage', ResourceUsageViewSet, basename='resourceusage')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'statistics', ServerStatisticsViewSet, basename='statistics')
router.register(r'mods', ModViewSet, basename='mod')
router.register(r'events', ServerEventViewSet, basename='event')

app_name = 'backend'

urlpatterns = [
    path('', api_overview, name='api-overview'),
    path('dashboard/', dashboard_stats, name='dashboard-stats'),
    
    # Plugin API endpoints
    path('plugins/search/', search_plugins, name='search-plugins'),
    path('plugins/<str:source>/<str:plugin_id>/', plugin_details, name='plugin-details'),
    path('servers/<int:server_id>/plugins/install/', install_plugin, name='install-plugin'),
    path('servers/<int:server_id>/plugins/<int:plugin_id>/uninstall/', uninstall_plugin, name='uninstall-plugin'),
    path('servers/<int:server_id>/plugins/<int:plugin_id>/toggle/', toggle_plugin, name='toggle-plugin'),
    
    path('', include(router.urls)),
]
