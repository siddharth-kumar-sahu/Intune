from django.db import models

from intune.models.base import BaseModel
from pgvector.django import VectorField


class Document(BaseModel):
    team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name="documents")
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/")
    metadata = models.JSONField(blank=True, null=True)
    size = models.BigIntegerField(blank=True, null=True)
    content_type = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "documents"

    def html_document_link(self):
        return f'<a href="{self.file.url}" target="_blank">{self.name}</a>'


class DocumentChunk(BaseModel):
    document = models.ForeignKey(
        "Document", on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_index = models.IntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=1536)

    class Meta:
        db_table = "document_chunks"
