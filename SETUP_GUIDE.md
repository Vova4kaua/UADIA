# Minecraft Server Panel - Setup Instructions

## Встановлення залежностей

1. Встановіть залежності Python:
```bash
pip install -r requirements.txt
```

## Налаштування

1. Запустіть міграції:
```bash
python manage.py makemigrations
python manage.py migrate
```

2. Створіть superuser (якщо потрібно):
```bash
python manage.py createsuperuser
```

## Запуск серверу

### Для розробки (з підтримкою WebSocket):
```bash
python manage.py runserver
```

Або через Daphne (ASGI сервер):
```bash
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

## Нові можливості

### 1. API для плагінів

**Пошук плагінів:**
```
GET /api/plugins/search/?source=modrinth&q=worldedit&limit=20
```

Підтримувані джерела:
- `modrinth` - Modrinth API
- `spigot` - Spigot/Spiget API
- `hangar` - Hangar (PaperMC) API

**Детальна інформація про плагін:**
```
GET /api/plugins/{source}/{plugin_id}/
```

**Встановлення плагіну:**
```
POST /api/servers/{server_id}/plugins/install/
{
    "source": "modrinth",
    "plugin_id": "worldedit",
    "version": "7.2.15"  // optional
}
```

**Видалення плагіну:**
```
DELETE /api/servers/{server_id}/plugins/{plugin_id}/uninstall/
```

**Увімкнути/вимкнути плагін:**
```
POST /api/servers/{server_id}/plugins/{plugin_id}/toggle/
```

### 2. WebSocket для консолі

**Підключення:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/console/{server_id}/');

ws.onopen = () => {
    console.log('Connected to console');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Log:', data.message);
};

// Відправка команди
ws.send(JSON.stringify({
    type: 'command',
    command: 'say Hello World'
}));

// Отримання історії логів
ws.send(JSON.stringify({
    type: 'get_history'
}));
```

**Формат повідомлень:**
```javascript
// Вхідні повідомлення (від сервера)
{
    type: 'log',
    message: 'Server started',
    log_level: 'INFO',  // INFO, WARN, ERROR, DEBUG, SUCCESS, COMMAND
    timestamp: '2026-01-04T12:00:00'
}

{
    type: 'error',
    message: 'Error description'
}

{
    type: 'info',
    message: 'Info message'
}

// Вихідні повідомлення (до сервера)
{
    type: 'command',
    command: 'stop'
}

{
    type: 'get_history'
}
```

### 3. WebSocket для статистики

**Підключення:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/stats/{server_id}/');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // data.data містить статистику
    console.log('CPU:', data.data.cpu_percent);
    console.log('Memory:', data.data.memory_mb);
};
```

**Формат даних:**
```javascript
{
    type: 'stats',
    data: {
        cpu_percent: 45.2,
        memory_mb: 1024.5,
        memory_limit_mb: 2048,
        memory_percent: 50.0,
        online: true
    }
}
```

## Оновлення frontend

Оновлені сторінки:
- `/panel/` - Головна панель з новим дизайном
- `/panel/servers/{id}/` - Сторінка сервера з консоллю в реальному часі
- `/panel/servers/{id}/plugins/` - Менеджер плагінів з пошуком
- `/panel/servers/{id}/logs/` - Сторінка логів з фільтрацією

## Troubleshooting

### Помилка "channels not found"
Встановіть channels:
```bash
pip install channels channels-redis daphne
```

### Помилка "aiohttp not found"
Встановіть aiohttp:
```bash
pip install aiohttp
```

### WebSocket не підключається
Переконайтеся що використовуєте Daphne або runserver Django 5.0+:
```bash
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

### Docker не працює
Переконайтеся що Docker Desktop запущений:
```bash
docker ps
```

## Майбутні покращення

- Redis для CHANNEL_LAYERS (production)
- Автентифікація для WebSocket
- Більше джерел плагінів (Bukkit DevBukkit, CurseForge)
- Автоматичне оновлення плагінів
- Система залежностей плагінів
- Файловий менеджер
- Система бекапів
