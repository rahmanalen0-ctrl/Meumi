from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings
from datetime import timedelta
import os
import hashlib

from .models import User, Conversation, Message, FileMessage, Participant, DeliveryReceipt
from .serializers import (
    UserSerializer, ConversationSerializer, MessageSerializer,
    FileMessageSerializer, DeliveryReceiptSerializer
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=False, methods=['post'])
    def signup(self, request):
        username = request.data.get('username', '').strip()
        if not username:
            return Response({'error': 'Username required'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create(username=username, last_activity=timezone.now(), is_online=True)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def login(self, request):
        username = request.data.get('username', '').strip()
        if not username:
            return Response({'error': 'Username required'}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'last_activity': timezone.now(), 'is_online': True}
        )
        
        # Always update activity on login
        user.last_activity = timezone.now()
        user.is_online = True
        user.save(update_fields=['last_activity', 'is_online'])
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def track_activity(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
            user.last_activity = timezone.now()
            user.is_online = True
            user.save()
            return Response({'status': 'updated'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def logout(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
            user.is_online = False
            user.save(update_fields=['is_online'])
            return Response({'status': 'logged out'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def list_users(self, request):
        users = User.objects.all().order_by('-last_activity')
        return Response(UserSerializer(users, many=True).data)


class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer

    @action(detail=False, methods=['post'])
    def get_or_create(self, request):
        user_id = request.data.get('user_id')
        other_user_id = request.data.get('other_user_id')

        if not user_id or not other_user_id:
            return Response({'error': 'user_id and other_user_id required'}, status=status.HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User, id=user_id)
        other_user = get_object_or_404(User, id=other_user_id)

        conversations = Conversation.objects.filter(
            type='one_to_one',
            participant__user=user
        ).filter(
            participant__user=other_user
        ).distinct()

        if conversations.exists():
            conv = conversations.first()
        else:
            conv = Conversation.objects.create(type='one_to_one')
            Participant.objects.create(conversation=conv, user=user)
            Participant.objects.create(conversation=conv, user=other_user)

        return Response(ConversationSerializer(conv).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def messages(self, request, pk=None):
        conversation_id = request.query_params.get('conversation_id')
        if not conversation_id:
            return Response({'error': 'conversation_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        conversation = get_object_or_404(Conversation, id=conversation_id)
        messages = conversation.messages.filter(expires_at__gt=timezone.now())
        return Response(MessageSerializer(messages, many=True).data)

    @action(detail=False, methods=['get'])
    def by_user(self, request):
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = get_object_or_404(User, id=user_id)
        conversations = Conversation.objects.filter(
            participant__user=user
        ).select_related('group_admin').prefetch_related(
            'participant_set__user', 'messages__sender'
        ).distinct().order_by('-created_at')
        return Response(ConversationSerializer(conversations, many=True).data)

    @action(detail=False, methods=['post'])
    def create_group(self, request):
        user_id = request.data.get('user_id')
        group_name = request.data.get('group_name', '').strip()
        group_privacy = request.data.get('group_privacy', 'public')
        group_member_limit = request.data.get('group_member_limit', 50)
        description = request.data.get('description', '').strip()
        member_ids = request.data.get('member_ids', [])

        if not user_id or not group_name:
            return Response({'error': 'user_id and group_name required'}, status=status.HTTP_400_BAD_REQUEST)

        if group_privacy not in ['public', 'invite', 'closed']:
            return Response({'error': 'Invalid group_privacy'}, status=status.HTTP_400_BAD_REQUEST)

        if group_member_limit not in [5, 10, 15, 50]:
            return Response({'error': 'Invalid group_member_limit. Must be 5, 10, 15, or 50'}, status=status.HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User, id=user_id)

        conv = Conversation.objects.create(
            type='group',
            name=group_name,
            description=description,
            group_privacy=group_privacy,
            group_member_limit=group_member_limit,
            group_admin=user
        )

        Participant.objects.create(conversation=conv, user=user)

        for member_id in member_ids:
            try:
                member = User.objects.get(id=member_id)
                if conv.participant_set.count() < group_member_limit:
                    Participant.objects.create(conversation=conv, user=member)
            except User.DoesNotExist:
                pass

        return Response(ConversationSerializer(conv).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        conversation = self.get_object()
        user_id = request.data.get('user_id')
        requester_id = request.data.get('requester_id')

        if not conversation.type == 'group':
            return Response({'error': 'Only group conversations allowed'}, status=status.HTTP_400_BAD_REQUEST)

        if conversation.group_privacy == 'closed':
            requester = get_object_or_404(User, id=requester_id)
            if conversation.group_admin != requester:
                return Response({'error': 'Only admin can add members to closed group'}, status=status.HTTP_403_FORBIDDEN)

        if conversation.participant_set.count() >= conversation.group_member_limit:
            return Response({'error': f'Group is full. Max members: {conversation.group_member_limit}'}, status=status.HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User, id=user_id)

        if Participant.objects.filter(conversation=conversation, user=user).exists():
            return Response({'error': 'User already in group'}, status=status.HTTP_400_BAD_REQUEST)

        Participant.objects.create(conversation=conversation, user=user)

        return Response(ConversationSerializer(conversation).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        conversation = self.get_object()
        user_id = request.data.get('user_id')
        requester_id = request.data.get('requester_id')

        if not conversation.type == 'group':
            return Response({'error': 'Only group conversations allowed'}, status=status.HTTP_400_BAD_REQUEST)

        requester = get_object_or_404(User, id=requester_id)
        if conversation.group_admin != requester:
            return Response({'error': 'Only admin can remove members'}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=user_id)
        Participant.objects.filter(conversation=conversation, user=user).delete()

        return Response(ConversationSerializer(conversation).data, status=status.HTTP_200_OK)


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all().select_related('sender', 'conversation')
    serializer_class = MessageSerializer

    @action(detail=False, methods=['post'])
    def send(self, request):
        from datetime import timedelta
        from django.utils import timezone
        
        conversation_id = request.data.get('conversation_id')
        sender_id = request.data.get('sender_id')
        content = request.data.get('content', '').strip()
        content_type = request.data.get('content_type', 'text')

        if not conversation_id or not sender_id or not content:
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conversation = Conversation.objects.get(id=conversation_id)
            sender = User.objects.get(id=sender_id)
        except (Conversation.DoesNotExist, User.DoesNotExist):
            return Response({'error': 'Conversation or user not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if sender is a participant, if not add them
        if not Participant.objects.filter(conversation=conversation, user=sender).exists():
            Participant.objects.create(conversation=conversation, user=sender)

        expires_at = timezone.now() + timedelta(hours=sender.auto_delete_hours)

        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content,
            content_type=content_type,
            expires_at=expires_at
        )

        # Create delivery receipts for other participants
        for participant in conversation.participant_set.exclude(user=sender):
            DeliveryReceipt.objects.create(message=message, recipient=participant.user)

        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail='pk', methods=['post'])
    def mark_read(self, request, pk=None):
        message = self.get_object()
        user_id = request.data.get('user_id')
        user = get_object_or_404(User, id=user_id)

        receipt = DeliveryReceipt.objects.filter(message=message, recipient=user).first()
        if receipt:
            receipt.delivered = True
            receipt.delivered_at = timezone.now()
            receipt.read = True
            receipt.read_at = timezone.now()
            receipt.save()

        return Response({'status': 'marked as read'}, status=status.HTTP_200_OK)


class FileUploadViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'])
    def upload(self, request):
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        file_obj = request.FILES['file']
        conversation_id = request.data.get('conversation_id')
        sender_id = request.data.get('sender_id')

        # Validate required fields
        if not conversation_id:
            return Response({'error': 'conversation_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not sender_id:
            return Response({'error': 'sender_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file extension
        dangerous_extensions = ['exe', 'bat', 'cmd', 'com', 'scr', 'vbs', 'js', 'jar', 'zip']
        file_ext = file_obj.name.lower().split('.')[-1]
        if file_ext in dangerous_extensions:
            return Response({'error': f'File type .{file_ext} is not allowed'}, status=status.HTTP_400_BAD_REQUEST)

        MAX_FILE_SIZE = 1024 * 1024 * 1024
        if file_obj.size > MAX_FILE_SIZE:
            return Response({'error': f'File size exceeds {MAX_FILE_SIZE / (1024**3):.1f}GB limit'}, 
                          status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        try:
            # Validate conversation exists
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                return Response({'error': f'Conversation not found: {conversation_id}'}, status=status.HTTP_404_NOT_FOUND)

            # Validate sender exists
            try:
                sender = User.objects.get(id=sender_id)
            except User.DoesNotExist:
                return Response({'error': f'User not found: {sender_id}'}, status=status.HTTP_404_NOT_FOUND)

            # Calculate hash and reset file position after hashing
            file_hash = hashlib.sha256()
            file_obj.seek(0)  # Reset to beginning
            for chunk in file_obj.chunks():
                file_hash.update(chunk)
            file_obj.seek(0)  # Reset again before saving

            file_name = f"uploads/{conversation_id}/{file_hash.hexdigest()}_{file_obj.name}"
            file_path = default_storage.save(file_name, file_obj)

            # Ensure sender is a participant
            if not Participant.objects.filter(conversation=conversation, user=sender).exists():
                Participant.objects.create(conversation=conversation, user=sender)

            message = Message.objects.create(
                conversation=conversation,
                sender=sender,
                content=file_obj.name,
                content_type=self._get_content_type(file_obj.name)
            )

            file_msg = FileMessage.objects.create(
                message=message,
                storage_path=file_path,
                mime_type=file_obj.content_type,
                size_bytes=file_obj.size,
                hash=file_hash.hexdigest()
            )

            # Create delivery receipts for other participants
            for participant in conversation.participant_set.exclude(user=sender):
                DeliveryReceipt.objects.create(message=message, recipient=participant.user)

            return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

        except Conversation.DoesNotExist:
            return Response({'error': f'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({'error': f'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Upload error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def _get_content_type(filename):
        ext = filename.lower().split('.')[-1]
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return 'image'
        elif ext in ['mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'wmv']:
            return 'video'
        elif ext in ['mp3', 'wav', 'aac', 'flac', 'm4a', 'wma', 'ogg']:
            return 'audio'
        elif ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'zip', 'rar']:
            return 'file'
        return 'file'

    @action(detail=False, methods=['get'])
    def download(self, request):
        import base64
        
        file_id = request.query_params.get('file_id')
        file_msg = get_object_or_404(FileMessage, id=file_id)

        file_path = file_msg.storage_path
        if default_storage.exists(file_path):
            try:
                with default_storage.open(file_path, 'rb') as f:
                    file_content = f.read()
                
                # Encode to base64 for safe JSON transmission
                file_base64 = base64.b64encode(file_content).decode('utf-8')
                
                return Response({
                    'file': file_base64,
                    'filename': file_msg.message.content,
                    'mime_type': file_msg.mime_type,
                    'size': len(file_content)
                })
            except Exception as e:
                return Response({'error': f'Error reading file: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)
