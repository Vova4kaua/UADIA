from django.db import models

class Server(models.Model):
    # Выбор типа ядра сервера
    SERVER_TYPE_CHOICES = [
        ('VANILLA', 'Vanilla'),
        ('PAPER', 'Paper'),
        ('SPIGOT', 'Spigot'),
        ('BUKKIT', 'Bukkit'),
        ('FORGE', 'Forge'),
        ('FABRIC', 'Fabric'),
        ('PURPUR', 'Purpur'),
        ('FOLIA', 'Folia'),
        ('PUFFERFISH', 'Pufferfish'),
        ('AIRPLANE', 'Airplane'),
        ('MOHIST', 'Mohist (Forge + Bukkit)'),
        ('CATSERVER', 'CatServer (Forge + Bukkit)'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Название сервера")
    ip_address = models.GenericIPAddressField(verbose_name="IP адрес")
    port = models.IntegerField(verbose_name="Порт")
    is_online = models.BooleanField(default=False, verbose_name="Онлайн")
    
    # Новые поля
    server_type = models.CharField(
        max_length=20, 
        choices=SERVER_TYPE_CHOICES, 
        default='PAPER',
        verbose_name="Тип ядра"
    )
    minecraft_version = models.CharField(
        max_length=20, 
        default='1.20.1',
        verbose_name="Версия Minecraft",
        help_text="Например: 1.20.1, 1.19.4, 1.18.2"
    )
    memory = models.CharField(
        max_length=10,
        default='2G',
        verbose_name="Выделенная память",
        help_text="Например: 1G, 2G, 4G, 8G"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлен")

    class Meta:
        verbose_name = "Сервер"
        verbose_name_plural = "Серверы"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.server_type} {self.minecraft_version})"


class UserProfile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    favorite_server = models.ForeignKey(Server, on_delete=models.SET_NULL, null=True, blank=True)
    owned_servers = models.ManyToManyField(Server, related_name='owners', blank=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return self.user.username

    
class ServerLog(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    log_entry = models.TextField()

    class Meta:
        verbose_name = "Лог сервера"
        verbose_name_plural = "Логи серверов"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Log for {self.server.name} at {self.timestamp}"


class ServerSettings(models.Model):
    GAMEMODE_CHOICES = [
        ('survival', 'Выживание'),
        ('creative', 'Творчество'),
        ('adventure', 'Приключение'),
        ('spectator', 'Наблюдатель'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('peaceful', 'Мирный'),
        ('easy', 'Легкий'),
        ('normal', 'Нормальный'),
        ('hard', 'Сложный'),
    ]
    
    server = models.OneToOneField(Server, on_delete=models.CASCADE)
    max_players = models.IntegerField(default=20, verbose_name="Макс. игроков")
    motd = models.CharField(max_length=100, default="Welcome to the server!", verbose_name="MOTD")
    whitelist_enabled = models.BooleanField(default=False, verbose_name="Белый список")
    gamemode = models.CharField(max_length=20, choices=GAMEMODE_CHOICES, default='survival', verbose_name="Режим игры")
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='normal', verbose_name="Сложность")
    pvp_enabled = models.BooleanField(default=True, verbose_name="PVP")
    online_mode = models.BooleanField(default=True, verbose_name="Online mode")

    class Meta:
        verbose_name = "Настройки сервера"
        verbose_name_plural = "Настройки серверов"

    def __str__(self):
        return f"Settings for {self.server.name}"


class Plugin(models.Model):
    name = models.CharField(max_length=100)
    version = models.CharField(max_length=20)
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='plugins')
    enabled = models.BooleanField(default=True, verbose_name="Включен")
    file_path = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Плагин"
        verbose_name_plural = "Плагины"

    def __str__(self):
        return f"{self.name} v{self.version} for {self.server.name}"


class Backup(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='backups')
    created_at = models.DateTimeField(auto_now_add=True)
    file_path = models.CharField(max_length=255)
    size_bytes = models.BigIntegerField(default=0, verbose_name="Размер (байты)")

    class Meta:
        verbose_name = "Бэкап"
        verbose_name_plural = "Бэкапы"
        ordering = ['-created_at']

    def __str__(self):
        return f"Backup for {self.server.name} at {self.created_at}"
    
    
class ResourceUsage(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='resource_usages')
    timestamp = models.DateTimeField(auto_now_add=True)
    cpu_usage = models.FloatField()
    memory_usage = models.FloatField()
    disk_usage = models.FloatField()

    class Meta:
        verbose_name = "Использование ресурсов"
        verbose_name_plural = "Использование ресурсов"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Resource usage for {self.server.name} at {self.timestamp}"

    
class Notification(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username} at {self.created_at}"


class ServerStatistics(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='statistics')
    timestamp = models.DateTimeField(auto_now_add=True)
    active_players = models.IntegerField()
    uptime = models.DurationField()

    class Meta:
        verbose_name = "Статистика сервера"
        verbose_name_plural = "Статистика серверов"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Statistics for {self.server.name} at {self.timestamp}"

    
class Mod(models.Model):
    name = models.CharField(max_length=100)
    version = models.CharField(max_length=20)
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='mods')
    enabled = models.BooleanField(default=True, verbose_name="Включен")
    file_path = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Мод"
        verbose_name_plural = "Моды"

    def __str__(self):
        return f"{self.name} v{self.version} for {self.server.name}"

    
class ServerEvent(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=100)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Событие"
        verbose_name_plural = "События"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Event {self.event_type} for {self.server.name} at {self.timestamp}"
