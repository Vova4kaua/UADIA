from django.shortcuts import render, redirect
from django.views.generic import *
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.models import User
from backend.models import *

# Authentication Views

class RegisterView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('panel:server_list')
        form = UserCreationForm()
        return render(request, 'register.html', {'form': form})
    
    def post(self, request):
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Создаем профиль для пользователя
            UserProfile.objects.create(user=user)
            
            # Автоматический вход после регистрации
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            
            messages.success(request, f'Добро пожаловать, {username}! Ваш аккаунт создан.')
            return redirect('panel:server_list')
        return render(request, 'register.html', {'form': form})


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('panel:server_list')
        form = AuthenticationForm()
        return render(request, 'login.html', {'form': form})
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Создаем профиль если его нет
            UserProfile.objects.get_or_create(user=user)
            
            # Настройка сессии
            if not remember_me:
                request.session.set_expiry(0)  # Сессия до закрытия браузера
            
            messages.success(request, f'С возвращением, {username}!')
            
            # Перенаправление на запрошенную страницу или главную
            next_url = request.GET.get('next', 'panel:server_list')
            return redirect(next_url)
        else:
            messages.error(request, 'Неверное имя пользователя или пароль.')
            return render(request, 'login.html', {'form': AuthenticationForm()})


class LogoutView(View):
    def get(self, request):
        logout(request)
        messages.success(request, 'Вы успешно вышли из системы.')
        return redirect('panel:login')


# Panel Views with Authentication

class ServerListView(LoginRequiredMixin, ListView):
    model = Server
    template_name = 'server_list.html'
    context_object_name = 'servers'
    login_url = 'panel:login'
    
    def get_queryset(self):
        # Показываем только серверы пользователя
        user = self.request.user
        try:
            profile = user.userprofile
            return profile.owned_servers.all()
        except:
            return Server.objects.none()


class ServerCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'server_create.html'
    login_url = 'panel:login'


class ServerDetailView(LoginRequiredMixin, DetailView):
    model = Server
    template_name = 'server_detail.html'
    context_object_name = 'server'
    login_url = 'panel:login'
    
    def get_queryset(self):
        # Пользователь может видеть только свои серверы
        user = self.request.user
        try:
            profile = user.userprofile
            return profile.owned_servers.all()
        except:
            return Server.objects.none()


class UserProfileView(LoginRequiredMixin, DetailView):
    model = UserProfile
    template_name = 'user_profile.html'
    context_object_name = 'profile'
    login_url = 'panel:login'
    
    def get_object(self):
        # Показываем профиль текущего пользователя
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class ServerLogListView(LoginRequiredMixin, ListView):
    model = ServerLog
    template_name = 'server_logs.html'
    context_object_name = 'logs'
    login_url = 'panel:login'
    
    def get_queryset(self):
        server_id = self.kwargs['server_id']
        return ServerLog.objects.filter(server__id=server_id).order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['server_id'] = self.kwargs['server_id']
        return context


class ServerSettingsView(LoginRequiredMixin, DetailView):
    model = ServerSettings
    template_name = 'server_settings.html'
    context_object_name = 'settings'
    login_url = 'panel:login'
    
    def get_object(self):
        server_id = self.kwargs['server_id']
        try:
            return ServerSettings.objects.get(server__id=server_id)
        except ServerSettings.DoesNotExist:
            return None
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['server_id'] = self.kwargs['server_id']
        return context


class PluginListView(LoginRequiredMixin, ListView):
    model = Plugin
    template_name = 'plugins.html'
    context_object_name = 'plugins'
    login_url = 'panel:login'
    
    def get_queryset(self):
        server_id = self.kwargs['server_id']
        return Plugin.objects.filter(server__id=server_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['server_id'] = self.kwargs['server_id']
        return context


class PluginAddView(LoginRequiredMixin, TemplateView):
    template_name = 'plugin_add.html'
    login_url = 'panel:login'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['server_id'] = self.kwargs['server_id']
        return context


class BackupListView(LoginRequiredMixin, ListView):
    model = Backup
    template_name = 'backups.html'
    context_object_name = 'backups'
    login_url = 'panel:login'
    
    def get_queryset(self):
        server_id = self.kwargs['server_id']
        return Backup.objects.filter(server__id=server_id).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['server_id'] = self.kwargs['server_id']
        return context


class ResourceUsageListView(LoginRequiredMixin, ListView):
    model = ResourceUsage
    template_name = 'resource_usage.html'
    context_object_name = 'usages'
    login_url = 'panel:login'
    
    def get_queryset(self):
        server_id = self.kwargs['server_id']
        return ResourceUsage.objects.filter(server__id=server_id).order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['server_id'] = self.kwargs['server_id']
        return context
