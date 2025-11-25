from rest_framework import serializers
from .models import User, Conversation, Message, FileMessage, Participant, DeliveryReceipt
from django.utils import timezone
from datetime import timedelta


class UserSerializer(serializers.ModelSerializer):
    offline_minutes = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'avatar_url', 'created_at', 'is_online', 'last_activity', 'offline_minutes']

    def get_is_online(self, obj):
        now = timezone.now()
        thirty_mins_ago = now - timedelta(minutes=30)
        return obj.last_activity > thirty_mins_ago

    def get_offline_minutes(self, obj):
        now = timezone.now()
        delta = now - obj.last_activity
        total_seconds = int(delta.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        if minutes == 0:
            return f"{seconds}s"
        elif minutes < 60:
            return f"{minutes}m {seconds}s"
        else:
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours}h {mins}m {seconds}s"


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    file = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'content', 'content_type', 'sent_at', 'edited', 'edited_at', 'file']

    def get_file(self, obj):
        if hasattr(obj, 'file'):
            return FileMessageSerializer(obj.file).data
        return None


class FileMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileMessage
        fields = ['id', 'storage_path', 'mime_type', 'size_bytes']


class ParticipantSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Participant
        fields = ['user', 'joined_at']


class ConversationSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(source='participant_set', many=True, read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    group_admin = UserSerializer(read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'type', 'name', 'description', 'group_privacy', 'group_member_limit', 'group_admin', 'participants', 'messages', 'created_at']


class DeliveryReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryReceipt
        fields = ['id', 'message', 'recipient', 'delivered', 'read', 'delivered_at', 'read_at']
