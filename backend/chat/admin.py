from django.contrib import admin
from .models import User, Conversation, Participant, Message, FileMessage, DeliveryReceipt

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'created_at')
    search_fields = ('username',)

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'created_at')
    list_filter = ('type',)

@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('user', 'conversation', 'joined_at')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'conversation', 'content_type', 'sent_at')
    list_filter = ('content_type', 'sent_at')
    search_fields = ('sender__username', 'content')

@admin.register(FileMessage)
class FileMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'mime_type', 'size_bytes', 'uploaded_at')
    list_filter = ('mime_type',)

@admin.register(DeliveryReceipt)
class DeliveryReceiptAdmin(admin.ModelAdmin):
    list_display = ('message', 'recipient', 'delivered', 'read')
    list_filter = ('delivered', 'read')
