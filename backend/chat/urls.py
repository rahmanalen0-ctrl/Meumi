from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, ConversationViewSet, MessageViewSet, FileUploadViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'conversations', ConversationViewSet)
router.register(r'messages', MessageViewSet)
router.register(r'files', FileUploadViewSet, basename='file')

urlpatterns = [
    path('', include(router.urls)),
]
