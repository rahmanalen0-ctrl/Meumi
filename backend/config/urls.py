from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('chat.urls')),
    path('', TemplateView.as_view(template_name='index.html')),
]

if settings.DEBUG:
    import os
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=os.path.join(settings.BASE_DIR.parent, 'frontend', 'static'))
