from rest_framework import serializers
from django.contrib.auth.models import User
from .models import *


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'date_joined']
        read_only_fields = ['date_joined']


class ServerSerializer(serializers.ModelSerializer):
    owner_count = serializers.SerializerMethodField()
    plugin_count = serializers.SerializerMethodField()
    server_type_display = serializers.CharField(source='get_server_type_display', read_only=True)
    
    class Meta:
        model = Server
        fields = [
            'id', 'name', 'ip_address', 'port', 'is_online', 
            'server_type', 'server_type_display', 'minecraft_version', 
            'memory', 'owner_count', 'plugin_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
        
    def get_owner_count(self, obj):
        return obj.owners.count()
    
    def get_plugin_count(self, obj):
        return obj.plugins.count()


class ServerDetailSerializer(serializers.ModelSerializer):
    owners = UserSerializer(many=True, read_only=True)
    plugins = serializers.SerializerMethodField()
    settings = serializers.SerializerMethodField()
    server_type_display = serializers.CharField(source='get_server_type_display', read_only=True)
    
    class Meta:
        model = Server
        fields = [
            'id', 'name', 'ip_address', 'port', 'is_online',
            'server_type', 'server_type_display', 'minecraft_version',
            'memory', 'owners', 'plugins', 'settings',
            'created_at', 'updated_at'
        ]
    
    def get_plugins(self, obj):
        plugins = obj.plugins.all()
        return PluginSerializer(plugins, many=True).data
    
    def get_settings(self, obj):
        try:
            return ServerSettingsSerializer(obj.serversettings).data
        except ServerSettings.DoesNotExist:
            return None


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    favorite_server = ServerSerializer(read_only=True)
    owned_servers = ServerSerializer(many=True, read_only=True)
    server_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'favorite_server', 'owned_servers', 'server_count']
    
    def get_server_count(self, obj):
        return obj.owned_servers.count()


class ServerLogSerializer(serializers.ModelSerializer):
    server_name = serializers.CharField(source='server.name', read_only=True)
    
    class Meta:
        model = ServerLog
        fields = ['id', 'server', 'server_name', 'timestamp', 'log_entry']
        read_only_fields = ['timestamp']


class ServerSettingsSerializer(serializers.ModelSerializer):
    server_name = serializers.CharField(source='server.name', read_only=True)
    gamemode_display = serializers.CharField(source='get_gamemode_display', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)
    
    class Meta:
        model = ServerSettings
        fields = [
            'id', 'server', 'server_name', 'max_players', 'motd', 
            'whitelist_enabled', 'gamemode', 'gamemode_display',
            'difficulty', 'difficulty_display', 'pvp_enabled', 'online_mode'
        ]


class PluginSerializer(serializers.ModelSerializer):
    server_name = serializers.CharField(source='server.name', read_only=True)
    
    class Meta:
        model = Plugin
        fields = ['id', 'name', 'version', 'server', 'server_name', 'enabled', 'file_path']


class BackupSerializer(serializers.ModelSerializer):
    server_name = serializers.CharField(source='server.name', read_only=True)
    size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = Backup
        fields = ['id', 'server', 'server_name', 'created_at', 'file_path', 'size_bytes', 'size_mb']
        read_only_fields = ['created_at']
    
    def get_size_mb(self, obj):
        if obj.size_bytes > 0:
            return round(obj.size_bytes / (1024 * 1024), 2)
        return 0


class ResourceUsageSerializer(serializers.ModelSerializer):
    server_name = serializers.CharField(source='server.name', read_only=True)
    
    class Meta:
        model = ResourceUsage
        fields = ['id', 'server', 'server_name', 'timestamp', 'cpu_usage', 'memory_usage', 'disk_usage']
        read_only_fields = ['timestamp']


class NotificationSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Notification
        fields = ['id', 'user', 'user_username', 'message', 'created_at', 'read']
        read_only_fields = ['created_at']


class ServerStatisticsSerializer(serializers.ModelSerializer):
    server_name = serializers.CharField(source='server.name', read_only=True)
    uptime_hours = serializers.SerializerMethodField()
    
    class Meta:
        model = ServerStatistics
        fields = ['id', 'server', 'server_name', 'timestamp', 'active_players', 'uptime', 'uptime_hours']
        read_only_fields = ['timestamp']
    
    def get_uptime_hours(self, obj):
        return obj.uptime.total_seconds() / 3600


class ModSerializer(serializers.ModelSerializer):
    server_name = serializers.CharField(source='server.name', read_only=True)
    
    class Meta:
        model = Mod
        fields = ['id', 'name', 'version', 'server', 'server_name', 'enabled', 'file_path']


class ServerEventSerializer(serializers.ModelSerializer):
    server_name = serializers.CharField(source='server.name', read_only=True)
    
    class Meta:
        model = ServerEvent
        fields = ['id', 'server', 'server_name', 'event_type', 'description', 'timestamp']
        read_only_fields = ['timestamp']


class ServerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new server with Docker container"""
    
    class Meta:
        model = Server
        fields = ['name', 'port', 'server_type', 'minecraft_version', 'memory']
    
    def validate_port(self, value):
        """Проверка что порт не занят"""
        if Server.objects.filter(port=value).exists():
            raise serializers.ValidationError("Этот порт уже используется другим сервером")
        if value < 25565 or value > 35565:
            raise serializers.ValidationError("Порт должен быть между 25565 и 35565")
        return value
    
    def validate_memory(self, value):
        """Проверка формата памяти"""
        if not value.endswith(('M', 'G')):
            raise serializers.ValidationError("Память должна заканчиваться на M или G (например: 2G, 512M)")
        return value
    
    def create(self, validated_data):
        # Docker контейнер будет создан в view
        server = Server.objects.create(
            name=validated_data['name'],
            ip_address='0.0.0.0',  # Will be assigned after Docker creation
            port=validated_data['port'],
            server_type=validated_data.get('server_type', 'PAPER'),
            minecraft_version=validated_data.get('minecraft_version', '1.20.1'),
            memory=validated_data.get('memory', '2G'),
            is_online=False
        )
        return server


class ServerTypeChoicesSerializer(serializers.Serializer):
    """Serializer для получения списка доступных типов серверов"""
    value = serializers.CharField()
    label = serializers.CharField()


class MinecraftVersionsSerializer(serializers.Serializer):
    """Serializer для популярных версий Minecraft"""
    version = serializers.CharField()
    release_date = serializers.CharField()
    recommended = serializers.BooleanField(default=False)
