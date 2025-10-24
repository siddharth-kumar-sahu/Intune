import time
from celery import shared_task
from intune.models import Document, DocumentChunk
import httpx
from django.conf import settings
import pymupdf
from django.contrib import messages


def simple_chunk(text, num_chunks=5):
    """Split text into roughly equal chunks (by length)."""
    length = len(text)
    chunk_size = max(1, length // num_chunks)
    return [text[i : i + chunk_size].strip() for i in range(0, length, chunk_size)]


@shared_task
def process_document(document_id):
    document = Document.objects.filter(id=document_id).first()
    if not document:
        print(f"Document with ID {document_id} not found.")
        return

    print(f"Processing document: {document.name} (ID: {document.id})")

    content_type = document.content_type
    file_path = document.file.path

    # PDF
    if content_type == "application/pdf":
        doc = pymupdf.open(file_path)
        for page_number, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if not text:
                continue

            # # Remove excessive whitespace/newlines
            # text = " ".join(text.split())

            # # Split each page into ~5 chunks
            # chunks = simple_chunk(text, num_chunks=3)

            # # Send each chunk to Celery for async processing
            # for idx, chunk in enumerate(chunks, start=1):
            #     process_document_chunk.delay(document.id, idx, chunk)
            process_document_chunk.delay(document.id, page_number, text.strip())
        doc.close()

    # TXT or MD
    elif content_type in ["text/plain", "text/markdown", "text/md"]:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line_number, line in enumerate(lines, start=1):
                print(f"--- Line {line_number} ---\n{line.strip()}\n")

    else:
        print(f"Unsupported content type: {content_type}")


@shared_task
def process_document_chunk(document_id, chunk_index, text):
    print(f"Processing chunk {chunk_index} of document {document_id}...")
    open_ai_api_key = settings.OPENAI_API_KEY
    open_ai_url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {open_ai_api_key}",
    }
    json_data = {
        "input": text,
        "model": "text-embedding-ada-002",
        "encoding_format": "float",
    }
    response = httpx.post(open_ai_url, headers=headers, json=json_data)
    if not response.status_code == 200:
        print(
            f"Failed to get embedding for chunk {chunk_index} of document {document_id}."
        )
        return

    embedding = response.json()["data"][0]["embedding"]
    print(
        f"Embedding for chunk {chunk_index} of document {document_id} obtained and embedding are {embedding[:10]}..."
    )
    DocumentChunk.objects.create(
        document_id=document_id,
        chunk_index=chunk_index,
        text=text,
        embedding=embedding,
    )
