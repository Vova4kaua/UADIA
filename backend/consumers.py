import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from backend.models import Server, ServerLog
import docker
import logging

logger = logging.getLogger(__name__)


class ServerConsoleConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time server console"""
    
    async def connect(self):
        self.server_id = self.scope['url_route']['kwargs']['server_id']
        self.room_group_name = f'console_{self.server_id}'
        self.docker_client = None
        self.container = None
        self.log_task = None
        
        # Check if user has permission
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return
        
        server = await self.get_server()
        if not server:
            await self.close()
            return
        
        # Check if user owns or has access to the server
        has_access = await self.check_access(server, user)
        if not has_access:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Start streaming logs
        await self.start_log_stream()
    
    async def disconnect(self, close_code):
        # Stop log streaming
        if self.log_task:
            self.log_task.cancel()
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming commands"""
        try:
            data = json.loads(text_data)
            command_type = data.get('type')
            
            if command_type == 'command':
                command = data.get('command', '')
                await self.execute_command(command)
            elif command_type == 'get_history':
                await self.send_log_history()
        
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def execute_command(self, command):
        """Execute command in container"""
        try:
            container = await self.get_container()
            if not container:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Server container not found'
                }))
                return
            
            # Execute command in container
            exec_result = await asyncio.to_thread(
                container.exec_run,
                f"echo '{command}' > /minecraft/stdin",
                privileged=True
            )
            
            # Log the command
            await self.save_log('COMMAND', f'> {command}')
            
            # Broadcast command to all connected clients
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'console_message',
                    'message': f'> {command}',
                    'log_level': 'COMMAND',
                    'timestamp': self.get_timestamp()
                }
            )
        
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to execute command: {str(e)}'
            }))
    
    async def start_log_stream(self):
        """Start streaming logs from container"""
        try:
            container = await self.get_container()
            if not container:
                await self.send(text_data=json.dumps({
                    'type': 'info',
                    'message': 'Server is not running'
                }))
                return
            
            # Create task for streaming logs
            self.log_task = asyncio.create_task(self.stream_logs(container))
        
        except Exception as e:
            logger.error(f"Error starting log stream: {e}")
    
    async def stream_logs(self, container):
        """Stream logs from container"""
        try:
            # Get log stream
            logs = await asyncio.to_thread(
                container.logs,
                stream=True,
                follow=True,
                tail=100
            )
            
            for log_bytes in logs:
                if self.log_task.cancelled():
                    break
                
                log_line = log_bytes.decode('utf-8').strip()
                if log_line:
                    # Parse log level
                    log_level = self.parse_log_level(log_line)
                    
                    # Save to database
                    await self.save_log(log_level, log_line)
                    
                    # Broadcast to all connected clients
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'console_message',
                            'message': log_line,
                            'log_level': log_level,
                            'timestamp': self.get_timestamp()
                        }
                    )
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.01)
        
        except asyncio.CancelledError:
            logger.info(f"Log streaming cancelled for server {self.server_id}")
        except Exception as e:
            logger.error(f"Error streaming logs: {e}")
    
    async def console_message(self, event):
        """Send message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'log',
            'message': event['message'],
            'log_level': event['log_level'],
            'timestamp': event['timestamp']
        }))
    
    async def send_log_history(self):
        """Send recent log history"""
        try:
            logs = await self.get_recent_logs(100)
            
            for log in logs:
                await self.send(text_data=json.dumps({
                    'type': 'log',
                    'message': log['message'],
                    'log_level': log['level'],
                    'timestamp': log['timestamp'].isoformat()
                }))
        
        except Exception as e:
            logger.error(f"Error sending log history: {e}")
    
    @database_sync_to_async
    def get_server(self):
        try:
            return Server.objects.get(id=self.server_id)
        except Server.DoesNotExist:
            return None
    
    @database_sync_to_async
    def check_access(self, server, user):
        return server.owner == user or user in server.owners.all()
    
    @database_sync_to_async
    def save_log(self, level, message):
        try:
            ServerLog.objects.create(
                server_id=self.server_id,
                level=level,
                message=message
            )
        except Exception as e:
            logger.error(f"Error saving log: {e}")
    
    @database_sync_to_async
    def get_recent_logs(self, limit):
        logs = ServerLog.objects.filter(
            server_id=self.server_id
        ).order_by('-timestamp')[:limit]
        
        return [
            {
                'message': log.message,
                'level': log.level,
                'timestamp': log.timestamp
            }
            for log in logs
        ]
    
    async def get_container(self):
        """Get Docker container for server"""
        try:
            if not self.container:
                self.docker_client = await asyncio.to_thread(docker.from_env)
                container_name = f"minecraft_server_{self.server_id}"
                self.container = await asyncio.to_thread(
                    self.docker_client.containers.get,
                    container_name
                )
            return self.container
        except Exception as e:
            logger.error(f"Error getting container: {e}")
            return None
    
    def parse_log_level(self, log_line):
        """Parse log level from log line"""
        log_upper = log_line.upper()
        
        if 'ERROR' in log_upper or 'SEVERE' in log_upper:
            return 'ERROR'
        elif 'WARN' in log_upper or 'WARNING' in log_upper:
            return 'WARN'
        elif 'DEBUG' in log_upper:
            return 'DEBUG'
        elif 'SUCCESS' in log_upper or 'DONE' in log_upper:
            return 'SUCCESS'
        else:
            return 'INFO'
    
    def get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()


class ServerStatsConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time server statistics"""
    
    async def connect(self):
        self.server_id = self.scope['url_route']['kwargs']['server_id']
        self.room_group_name = f'stats_{self.server_id}'
        self.stats_task = None
        
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Start sending stats
        self.stats_task = asyncio.create_task(self.send_stats_loop())
    
    async def disconnect(self, close_code):
        if self.stats_task:
            self.stats_task.cancel()
        
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def send_stats_loop(self):
        """Send stats every 2 seconds"""
        try:
            while True:
                stats = await self.get_server_stats()
                
                await self.send(text_data=json.dumps({
                    'type': 'stats',
                    'data': stats
                }))
                
                await asyncio.sleep(2)
        
        except asyncio.CancelledError:
            logger.info(f"Stats streaming cancelled for server {self.server_id}")
        except Exception as e:
            logger.error(f"Error in stats loop: {e}")
    
    async def get_server_stats(self):
        """Get current server statistics"""
        try:
            docker_client = await asyncio.to_thread(docker.from_env)
            container_name = f"minecraft_server_{self.server_id}"
            container = await asyncio.to_thread(
                docker_client.containers.get,
                container_name
            )
            
            # Get container stats
            stats = await asyncio.to_thread(
                container.stats,
                stream=False
            )
            
            # Calculate CPU usage
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0
            
            # Calculate memory usage
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            memory_percent = (memory_usage / memory_limit) * 100.0
            
            return {
                'cpu_percent': round(cpu_percent, 2),
                'memory_mb': round(memory_usage / (1024 * 1024), 2),
                'memory_limit_mb': round(memory_limit / (1024 * 1024), 2),
                'memory_percent': round(memory_percent, 2),
                'online': True
            }
        
        except Exception as e:
            logger.error(f"Error getting server stats: {e}")
            return {
                'cpu_percent': 0,
                'memory_mb': 0,
                'memory_limit_mb': 0,
                'memory_percent': 0,
                'online': False
            }
