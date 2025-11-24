from django.db import models
from django.utils import timezone
import uuid

class User(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    avatar_url = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    auto_delete_hours = models.IntegerField(default=3)
    last_activity = models.DateTimeField(default=timezone.now)
    is_online = models.BooleanField(default=True)

    def __str__(self):
        return self.username


class Conversation(models.Model):
    TYPE_CHOICES = [('one_to_one', 'One to One'), ('group', 'Group')]
    GROUP_PRIVACY_CHOICES = [
        ('public', 'Public - Anyone can join'),
        ('invite', 'Invite Only - Need invite to join'),
        ('closed', 'Closed - Admin only'),
    ]
    GROUP_MEMBER_LIMITS = {
        15: '15 members',
        5: '5 members',
        10: '10 members',
        50: '50 members',
    }
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='one_to_one')
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    group_privacy = models.CharField(max_length=20, choices=GROUP_PRIVACY_CHOICES, default='public', blank=True, null=True)
    group_member_limit = models.IntegerField(default=50, blank=True, null=True)
    group_admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_of')
    participants = models.ManyToManyField(User, through='Participant')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name or self.id}"


class Participant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('conversation', 'user')

    def __str__(self):
        return f"{self.user.username} in {self.conversation.id}"


class Message(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('text', 'Text'),
        ('file', 'File'),
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='text')
    sent_at = models.DateTimeField(auto_now_add=True)
    edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"Message from {self.sender.username} at {self.sent_at}"


class FileMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='file')
    storage_path = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.BigIntegerField()
    hash = models.CharField(max_length=64, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"File {self.id}"


class DeliveryReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='receipts')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)
    delivered = models.BooleanField(default=False)
    read = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('message', 'recipient')

    def __str__(self):
        return f"Receipt for message {self.message.id} to {self.recipient.username}"
