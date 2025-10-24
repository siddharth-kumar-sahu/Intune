from django.db import models
from intune.models.base import BaseModel


class Chat(BaseModel):
    title = models.CharField(max_length=255)
    team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name="chats")
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name="chats")
    is_conversation_active = models.BooleanField(default=False)

    class Meta:
        db_table = "chats"


class ChatConversation(BaseModel):
    chat = models.ForeignKey(
        "Chat", on_delete=models.CASCADE, related_name="conversations"
    )
    sender = models.CharField(max_length=16, choices=[("user", "User"), ("bot", "Bot")])
    message = models.TextField()

    class Meta:
        db_table = "chat_conversations"
