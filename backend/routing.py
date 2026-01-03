from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/console/(?P<server_id>\d+)/$', consumers.ServerConsoleConsumer.as_asgi()),
    re_path(r'ws/stats/(?P<server_id>\d+)/$', consumers.ServerStatsConsumer.as_asgi()),
]
