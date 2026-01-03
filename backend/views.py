from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from .models import *
from .serializers import *
from .plugin_api import plugin_manager
import docker
import os
import asyncio
from asgiref.sync import async_to_sync

try:
    docker_client = docker.from_env()
except Exception as e:
    docker_client = None
    print(f"Docker client initialization failed: {e}")


SERVER_TYPE_MAPPING = {
    'VANILLA': 'VANILLA',
    'PAPER': 'PAPER',
    'SPIGOT': 'SPIGOT',
    'BUKKIT': 'BUKKIT',
    'FORGE': 'FORGE',
    'FABRIC': 'FABRIC',
    'PURPUR': 'PURPUR',
    'FOLIA': 'FOLIA',
    'PUFFERFISH': 'PUFFERFISH',
    'AIRPLANE': 'AIRPLANE',
    'MOHIST': 'MOHIST',
    'CATSERVER': 'CATSERVER',
}


class ServerViewSet(viewsets.ModelViewSet):
    queryset = Server.objects.all().annotate(
        owner_count=Count('owners'),
        plugin_count=Count('plugins')
    )
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_online', 'port', 'server_type', 'minecraft_version']
    search_fields = ['name', 'ip_address', 'minecraft_version']
    ordering_fields = ['name', 'port', 'is_online', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ServerDetailSerializer
        elif self.action == 'create':
            return ServerCreateSerializer
        return ServerSerializer
    
    def perform_create(self, serializer):
        server = serializer.save()
        
        if self.request.user.is_authenticated:
            profile, created = UserProfile.objects.get_or_create(user=self.request.user)
            profile.owned_servers.add(server)
        
        self._create_docker_container(server)
        
        ServerSettings.objects.create(
            server=server,
            max_players=20,
            motd=f"Welcome to {server.name}!"
        )
    
    def _create_docker_container(self, server):
        if not docker_client:
            return
        
        try:
            container_name = f"minecraft-server-{server.id}"
            
            docker_type = SERVER_TYPE_MAPPING.get(server.server_type, 'PAPER')
            
            environment = {
                "EULA": "TRUE",
                "TYPE": docker_type,
                "VERSION": server.minecraft_version,
                "MEMORY": server.memory,
                "SERVER_NAME": server.name,
                "ENABLE_RCON": "true",
                "RCON_PASSWORD": f"rcon_{server.id}",
                "RCON_PORT": str(25575 + server.id),
            }
            
            if server.server_type in ['FORGE', 'FABRIC', 'MOHIST', 'CATSERVER']:
                environment["FORCE_REDOWNLOAD"] = "false"
            
            container = docker_client.containers.run(
                "itzg/minecraft-server",
                name=container_name,
                environment=environment,
                ports={
                    '25565/tcp': server.port,
                    f'{25575 + server.id}/tcp': 25575 + server.id  # RCON port
                },
                volumes={
                    f"minecraft-data-{server.id}": {
                        'bind': '/data',
                        'mode': 'rw'
                    }
                },
                detach=True,
                restart_policy={"Name": "unless-stopped"}
            )
            
            container.reload()
            server.ip_address = container.attrs['NetworkSettings']['IPAddress'] or '127.0.0.1'
            server.save()
            
            ServerEvent.objects.create(
                server=server,
                event_type="SERVER_CREATE",
                description=f"Server {server.name} created with {server.server_type} {server.minecraft_version}"
            )
            
        except Exception as e:
            print(f"Failed to create Docker container: {e}")
            ServerEvent.objects.create(
                server=server,
                event_type="SERVER_CREATE_ERROR",
                description=f"Failed to create server: {str(e)}"
            )
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        server = self.get_object()
        
        if not docker_client:
            return Response(
                {"error": "Docker client not available"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        try:
            container_name = f"minecraft-server-{server.id}"
            container = docker_client.containers.get(container_name)
            container.start()
            
            server.is_online = True
            server.save()
            
            ServerEvent.objects.create(
                server=server,
                event_type="SERVER_START",
                description=f"Server {server.name} started by {request.user.username if request.user.is_authenticated else 'Anonymous'}"
            )
            
            return Response({
                "status": "Server started successfully",
                "server": ServerSerializer(server).data
            })
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        server = self.get_object()
        
        if not docker_client:
            return Response(
                {"error": "Docker client not available"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        try:
            container_name = f"minecraft-server-{server.id}"
            container = docker_client.containers.get(container_name)
            container.stop()
            
            server.is_online = False
            server.save()
            
            ServerEvent.objects.create(
                server=server,
                event_type="SERVER_STOP",
                description=f"Server {server.name} stopped by {request.user.username if request.user.is_authenticated else 'Anonymous'}"
            )
            
            return Response({
                "status": "Server stopped successfully",
                "server": ServerSerializer(server).data
            })
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def restart(self, request, pk=None):
        server = self.get_object()
        
        if not docker_client:
            return Response(
                {"error": "Docker client not available"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        try:
            container_name = f"minecraft-server-{server.id}"
            container = docker_client.containers.get(container_name)
            container.restart()
            
            server.is_online = True
            server.save()
            
            ServerEvent.objects.create(
                server=server,
                event_type="SERVER_RESTART",
                description=f"Server {server.name} restarted by {request.user.username if request.user.is_authenticated else 'Anonymous'}"
            )
            
            return Response({
                "status": "Server restarted successfully",
                "server": ServerSerializer(server).data
            })
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        server = self.get_object()
        stats = ServerStatistics.objects.filter(server=server).order_by('-timestamp')[:24]
        serializer = ServerStatisticsSerializer(stats, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        server = self.get_object()
        
        if not docker_client:
            return Response(
                {"error": "Docker client not available"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        try:
            container_name = f"minecraft-server-{server.id}"
            container = docker_client.containers.get(container_name)
            logs = container.logs(tail=100).decode('utf-8')
            
            return Response({"logs": logs.split('\n')})
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def available_types(self, request):
        types = [
            {"value": choice[0], "label": choice[1]}
            for choice in Server.SERVER_TYPE_CHOICES
        ]
        return Response(types)
    
    @action(detail=False, methods=['get'])
    def available_versions(self, request):
        versions = [
            {"version": "1.21.1", "release_date": "2024-08", "recommended": True},
            {"version": "1.20.6", "release_date": "2024-04", "recommended": False},
            {"version": "1.20.4", "release_date": "2023-12", "recommended": False},
            {"version": "1.20.2", "release_date": "2023-09", "recommended": False},
            {"version": "1.20.1", "release_date": "2023-06", "recommended": True},
            {"version": "1.19.4", "release_date": "2023-03", "recommended": False},
            {"version": "1.19.2", "release_date": "2022-08", "recommended": True},
            {"version": "1.18.2", "release_date": "2022-02", "recommended": True},
            {"version": "1.17.1", "release_date": "2021-07", "recommended": False},
            {"version": "1.16.5", "release_date": "2021-01", "recommended": True},
            {"version": "1.12.2", "release_date": "2017-09", "recommended": True},
            {"version": "1.8.9", "release_date": "2015-12", "recommended": False},
        ]
        return Response(versions)


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(profile)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def set_favorite_server(self, request):
        server_id = request.data.get('server_id')
        
        try:
            server = Server.objects.get(id=server_id)
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.favorite_server = server
            profile.save()
            
            return Response({"status": "Favorite server updated"})
        except Server.DoesNotExist:
            return Response(
                {"error": "Server not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class ServerLogViewSet(viewsets.ModelViewSet):
    queryset = ServerLog.objects.all().order_by('-timestamp')
    serializer_class = ServerLogSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['server']


class ServerSettingsViewSet(viewsets.ModelViewSet):
    queryset = ServerSettings.objects.all()
    serializer_class = ServerSettingsSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class PluginViewSet(viewsets.ModelViewSet):
    queryset = Plugin.objects.all()
    serializer_class = PluginSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['server', 'enabled']
    search_fields = ['name', 'version']
    
    @action(detail=True, methods=['post'])
    def install(self, request, pk=None):
        plugin = self.get_object()
        return Response({"status": "Plugin installation started"})
    
    @action(detail=True, methods=['post'])
    def uninstall(self, request, pk=None):
        plugin = self.get_object()
        plugin.delete()
        return Response({"status": "Plugin uninstalled"})


class BackupViewSet(viewsets.ModelViewSet):
    queryset = Backup.objects.all().order_by('-created_at')
    serializer_class = BackupSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['server']
    
    @action(detail=False, methods=['post'])
    def create_backup(self, request):
        server_id = request.data.get('server_id')
        
        try:
            server = Server.objects.get(id=server_id)
            
            if not docker_client:
                return Response(
                    {"error": "Docker client not available"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            backup = Backup.objects.create(
                server=server,
                file_path=f"/backups/{server.name}_{server.id}_backup.tar.gz"
            )
            
            serializer = self.get_serializer(backup)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Server.DoesNotExist:
            return Response(
                {"error": "Server not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        backup = self.get_object()
        return Response({"status": "Backup restoration started"})


class ResourceUsageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ResourceUsage.objects.all().order_by('-timestamp')
    serializer_class = ResourceUsageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['server']
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        server_id = request.query_params.get('server_id')
        
        if server_id:
            latest = ResourceUsage.objects.filter(server_id=server_id).order_by('-timestamp').first()
            if latest:
                serializer = self.get_serializer(latest)
                return Response(serializer.data)
            return Response({"error": "No data available"}, status=status.HTTP_404_NOT_FOUND)
        
        latest_usages = []
        for server in Server.objects.all():
            usage = ResourceUsage.objects.filter(server=server).order_by('-timestamp').first()
            if usage:
                latest_usages.append(usage)
        
        serializer = self.get_serializer(latest_usages, many=True)
        return Response(serializer.data)


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all().order_by('-created_at')
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        unread = self.get_queryset().filter(read=False)
        serializer = self.get_serializer(unread, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.read = True
        notification.save()
        return Response({"status": "Notification marked as read"})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().update(read=True)
        return Response({"status": "All notifications marked as read"})


class ServerStatisticsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServerStatistics.objects.all().order_by('-timestamp')
    serializer_class = ServerStatisticsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['server']


class ModViewSet(viewsets.ModelViewSet):
    queryset = Mod.objects.all()
    serializer_class = ModSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['server', 'enabled']
    search_fields = ['name', 'version']


class ServerEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServerEvent.objects.all().order_by('-timestamp')
    serializer_class = ServerEventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['server', 'event_type']


@api_view(['GET'])
def api_overview(self, request):
    endpoints = {
        "servers": "/api/servers/",
        "server-detail": "/api/servers/{id}/",
        "server-types": "/api/servers/available_types/",
        "minecraft-versions": "/api/servers/available_versions/",
        "server-start": "/api/servers/{id}/start/",
        "server-stop": "/api/servers/{id}/stop/",
        "server-restart": "/api/servers/{id}/restart/",
        "server-stats": "/api/servers/{id}/stats/",
        "server-logs": "/api/servers/{id}/logs/",
        "profiles": "/api/profiles/",
        "my-profile": "/api/profiles/me/",
        "server-logs": "/api/server-logs/",
        "settings": "/api/settings/",
        "plugins": "/api/plugins/",
        "backups": "/api/backups/",
        "create-backup": "/api/backups/create_backup/",
        "resource-usage": "/api/resource-usage/",
        "current-usage": "/api/resource-usage/current/",
        "notifications": "/api/notifications/",
        "unread-notifications": "/api/notifications/unread/",
        "statistics": "/api/statistics/",
        "mods": "/api/mods/",
        "events": "/api/events/",
    }
    return Response({
        "message": "Minecraft Server Panel API",
        "version": "1.0",
        "endpoints": endpoints
    })


@api_view(['GET'])
def dashboard_stats(request):
    stats = {
        "total_servers": Server.objects.count(),
        "online_servers": Server.objects.filter(is_online=True).count(),
        "total_users": UserProfile.objects.count(),
        "total_plugins": Plugin.objects.count(),
        "total_backups": Backup.objects.count(),
        "server_types": {
            type_choice[0]: Server.objects.filter(server_type=type_choice[0]).count()
            for type_choice in Server.SERVER_TYPE_CHOICES
        },
        "recent_events": ServerEventSerializer(
            ServerEvent.objects.order_by('-timestamp')[:5],
            many=True
        ).data
    }
    return Response(stats)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_plugins(request):
    """Search plugins from various sources"""
    source = request.GET.get('source', 'modrinth')
    query = request.GET.get('q', '')
    category = request.GET.get('category', None)
    limit = int(request.GET.get('limit', 20))
    
    try:
        results = async_to_sync(plugin_manager.search)(
            source, query, category, limit
        )
        return Response({
            "source": source,
            "query": query,
            "results": results
        })
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def plugin_details(request, source, plugin_id):
    """Get detailed information about a plugin"""
    try:
        details = async_to_sync(plugin_manager.get_plugin_details)(
            source, plugin_id
        )
        if details:
            return Response(details)
        return Response(
            {"error": "Plugin not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def install_plugin(request, server_id):
    """Install a plugin on a server"""
    try:
        server = Server.objects.get(id=server_id)
        
        # Check permissions
        if server.owner != request.user and request.user not in server.owners.all():
            return Response(
                {"error": "You don't have permission to install plugins on this server"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        source = request.data.get('source')
        plugin_id = request.data.get('plugin_id')
        version = request.data.get('version', None)
        
        if not source or not plugin_id:
            return Response(
                {"error": "source and plugin_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get plugin details
        details = async_to_sync(plugin_manager.get_plugin_details)(source, plugin_id)
        if not details:
            return Response(
                {"error": "Plugin not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Download plugin
        plugin_data = async_to_sync(plugin_manager.download_plugin)(source, plugin_id, version)
        if not plugin_data:
            return Response(
                {"error": "Failed to download plugin"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Save plugin to server's plugins directory
        server_dir = f"/opt/minecraft/servers/server_{server.id}"
        plugins_dir = os.path.join(server_dir, "plugins")
        os.makedirs(plugins_dir, exist_ok=True)
        
        plugin_filename = f"{details['name']}.jar"
        plugin_path = os.path.join(plugins_dir, plugin_filename)
        
        with open(plugin_path, 'wb') as f:
            f.write(plugin_data)
        
        # Create plugin record in database
        plugin, created = Plugin.objects.get_or_create(
            server=server,
            name=details['name'],
            defaults={
                'version': version or details.get('versions', [{}])[0].get('name', 'latest'),
                'enabled': True,
                'description': details.get('description', ''),
                'author': details.get('author', 'Unknown'),
                'file_path': plugin_path
            }
        )
        
        if not created:
            plugin.version = version or details.get('versions', [{}])[0].get('name', 'latest')
            plugin.enabled = True
            plugin.file_path = plugin_path
            plugin.save()
        
        return Response({
            "status": "Plugin installed successfully",
            "plugin": PluginSerializer(plugin).data
        })
        
    except Server.DoesNotExist:
        return Response(
            {"error": "Server not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def uninstall_plugin(request, server_id, plugin_id):
    """Uninstall a plugin from a server"""
    try:
        server = Server.objects.get(id=server_id)
        plugin = Plugin.objects.get(id=plugin_id, server=server)
        
        # Check permissions
        if server.owner != request.user and request.user not in server.owners.all():
            return Response(
                {"error": "You don't have permission to uninstall plugins on this server"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete plugin file
        if plugin.file_path and os.path.exists(plugin.file_path):
            os.remove(plugin.file_path)
        
        # Delete from database
        plugin.delete()
        
        return Response({
            "status": "Plugin uninstalled successfully"
        })
        
    except (Server.DoesNotExist, Plugin.DoesNotExist):
        return Response(
            {"error": "Server or plugin not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_plugin(request, server_id, plugin_id):
    """Enable/disable a plugin"""
    try:
        server = Server.objects.get(id=server_id)
        plugin = Plugin.objects.get(id=plugin_id, server=server)
        
        # Check permissions
        if server.owner != request.user and request.user not in server.owners.all():
            return Response(
                {"error": "You don't have permission to modify plugins on this server"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        plugin.enabled = not plugin.enabled
        plugin.save()
        
        return Response({
            "status": f"Plugin {'enabled' if plugin.enabled else 'disabled'}",
            "plugin": PluginSerializer(plugin).data
        })
        
    except (Server.DoesNotExist, Plugin.DoesNotExist):
        return Response(
            {"error": "Server or plugin not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
