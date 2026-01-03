from django.urls import path, include

urlpatterns = [
    path('api/', include('backend.urls')),
    path('panel/', include('panel.urls')),
]
