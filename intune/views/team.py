import json
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from pgvector.django import CosineDistance

from intune.models import (
    Team,
    Document,
    Chat,
    ChatConversation,
    DocumentChunk,
    TeamMember,
)
from intune.tasks import process_document
from intune.utils import get_query_embedding, get_llm_response, get_chat_title_from_llm


class DashboardView(View):
    def get(self, request, *args, **kwargs):
        team = Team.objects.filter(
            id=kwargs.get("team_id"), members__user=request.user
        ).first()
        documents = Document.objects.filter(team=team).order_by("-created_at")
        context = {"team": team, "active": "dashboard", "documents": documents}
        return render(request, "team/dashboard.html", context)


class CreateTeamView(View):
    def post(self, request, *args, **kwargs):
        name = request.POST.get("name")
        description = request.POST.get("description")

        if Team.objects.filter(name=name).exists():
            messages.error(request, "A team with this name already exists.")
            return redirect("index")

        team = Team.objects.create(
            name=name,
            description=description,
            created_by=request.user,
        )
        TeamMember.objects.create(
            team=team,
            user=request.user,
            role="admin",
        )

        messages.success(request, f"Team '{team.name}' created successfully!")
        return redirect("index")


class UploadView(View):
    def get(self, request, *args, **kwargs):
        team = Team.objects.filter(
            id=kwargs.get("team_id"), members__user=request.user
        ).first()

        context = {
            "team": team,
            "active": "upload",
        }

        return render(request, "team/upload.html", context)

    def post(self, request, *args, **kwargs):
        team = Team.objects.filter(
            id=kwargs.get("team_id"), members__user=request.user
        ).first()

        uploaded_file = request.FILES.get("document")
        document = Document.objects.create(
            team=team,
            name=uploaded_file.name,
            file=uploaded_file,
            size=uploaded_file.size,
            content_type=uploaded_file.content_type,
        )
        process_document.delay(str(document.id))
        print("Queued document for processing : ", document.name)
        messages.success(
            request,
            f"Document {document.name} uploaded successfully and is being processed.",
        )
        context = {
            "team": team,
        }
        return render(request, "team/upload.html", context)


class ChatView(View):
    def get(self, request, *args, **kwargs):
        team = Team.objects.filter(
            id=kwargs.get("team_id"), members__user=request.user
        ).first()
        context = {
            "team": team,
            "active": "chat",
        }
        return render(request, "team/chat.html", context)

    def post(self, request, *args, **kwargs):
        team = Team.objects.filter(
            id=kwargs.get("team_id"), members__user=request.user
        ).first()

        query = request.POST.get("query")
        title = get_chat_title_from_llm(query.strip())
        chat = Chat.objects.create(
            team=team, user=request.user, title=title or "New Chat"
        )
        ChatConversation.objects.create(
            chat=chat,
            sender="user",
            message=query,
        )
        return redirect("chat-conversation", team_id=team.id, chat_id=chat.id)


class ChatConversationView(View):
    def get(self, request, *args, **kwargs):
        team = Team.objects.filter(
            id=kwargs.get("team_id"), members__user=request.user
        ).first()

        chat = Chat.objects.filter(
            id=kwargs.get("chat_id"), team=team, user=request.user
        ).first()
        previous_chats = Chat.objects.filter(team=team, user=request.user).order_by(
            "-created_at"
        )[:7]

        if not chat.is_conversation_active:
            # Step 1: Get the last conversation
            last_conversation = (
                ChatConversation.objects.filter(chat=chat)
                .order_by("-created_at")
                .first()
            )
            # Step 2: Get embedding of this last conversation from open ai
            query_embedding = get_query_embedding(last_conversation.message)

            # Step 3: Find relevant documents based on this embedding
            related_document_chunks = (
                DocumentChunk.objects.annotate(
                    distance=CosineDistance("embedding", query_embedding)
                )
                .filter(document__team=team)
                .select_related("document")
                .order_by("distance")[:4]
            )

            # Step 4: Build a richer context that includes document metadata for each chunk
            context_parts = []
            for i, chunk in enumerate(related_document_chunks):
                doc = getattr(chunk, "document", None)

                doc_id = getattr(doc, "id", "")
                doc_name = getattr(doc, "name", "Untitled")
                doc_file_name = getattr(getattr(doc, "file", None), "name", "") or ""
                doc_content_type = getattr(doc, "content_type", "") or ""
                doc_size = getattr(doc, "size", "") or ""
                doc_metadata = ""
                try:
                    if getattr(doc, "metadata", None):
                        doc_metadata = json.dumps(doc.metadata, ensure_ascii=False)
                except Exception:
                    doc_metadata = str(getattr(doc, "metadata", ""))

                doc_created_at = getattr(doc, "created_at", "")
                chunk_index = getattr(chunk, "chunk_index", i)
                distance = getattr(chunk, "distance", None)

                # Use your model method to build the HTML link; fallback if not available
                doc_html_link = ""
                try:
                    # html_document_link returns an <a href="...">name</a> string
                    doc_html_link = doc.html_document_link()
                except Exception:
                    # fallback: build a simple filename link if file has a url
                    file_url = getattr(getattr(doc, "file", None), "url", "")
                    if file_url:
                        doc_html_link = (
                            f'<a href="{file_url}" target="_blank">{doc_name}</a>'
                        )
                    else:
                        doc_html_link = doc_name

                header = (
                    f"Snippet {i+1}:\n"
                    f"Document id: {doc_id}\n"
                    f"Document name: {doc_name}\n"
                    f"Document file: {doc_file_name}\n"
                    f"Document content_type: {doc_content_type}\n"
                    f"Document size: {doc_size}\n"
                    f"Document metadata: {doc_metadata}\n"
                    f"Document created_at: {doc_created_at}\n"
                    f"Chunk index: {chunk_index}\n"
                    f"Embedding distance: {distance}\n"
                    f"Document html link: {doc_html_link}\n"
                )

                context_parts.append(header + "\n" + chunk.text.strip())

            context_text = "\n\n---\n\n".join(context_parts)
            user_query = last_conversation.message

            # Strict output format:
            # 1) One single paragraph answer (no line breaks)
            # 2) Followed by an HTML divider <hr/>
            # 3) Then a <div class="llm-sources"> block containing an ordered list <ol>
            #    where each <li> contains: the clickable HTML link, the doc+chunk tag, and "Confidence: XX%"
            # 4) Nothing else. If the answer is unknown, respond exactly: "I don't know." and still include the sources block (which can be empty)
            prompt = f"""
            You are an intelligent assistant that answers using ONLY the provided document snippets.

            Each snippet includes a "Document html link" field which contains a ready-to-use HTML <a> tag linking to that document. Use those links in the sources block below if you cite a document. Do NOT invent URLs.

            RESTRICTIONS:
            - Use ONLY the facts directly present in the snippets below. Do not hallucinate.
            - If the answer cannot be found in the provided context, reply exactly: "I don't know."
            - The output must follow the exact format described below (no extra commentary).

            CONTEXT:
            {context_text}

            USER QUESTION:
            {user_query}

            OUTPUT FORMAT (required):
            1) Provide a single, clear, factual paragraph answering the user's question. This paragraph must contain no line breaks.
            2) Immediately after the paragraph output a horizontal rule: <hr/>
            3) After the <hr/>, output an HTML sources block exactly as follows:

            <div class="llm-sources">
            <ol>
                <!-- For each source the model used, output one <li> -->
                <li> <document_html_link> — [sources: doc <doc_id> chunk <chunk_index>] — Confidence: <confidence>%</li>
                <!-- repeat for each used snippet -->
            </ol>
            </div>

            - <document_html_link> must be one of the "Document html link" strings provided in the snippet context (do not alter them).
            - <doc_id> and <chunk_index> must match the doc id and chunk index from the snippets.
            - <confidence> must be an integer between 0 and 100 representing the model's confidence that the cited snippet supports the answer (higher => more confident).
            - Only include snippets you actually relied on. Order them from most to least important.
            - If you answer "I don't know.", still include the sources block; it may be empty (<ol></ol>) or include the nearest matches the model inspected, but set confidence values appropriately (low if not confident).

            EXAMPLES (illustrative — do not output these examples):
            - Correct single-paragraph answer followed by sources block:
            <single paragraph here><hr/><div class="llm-sources"><ol><li><a href="...">Doc A</a> — [sources: doc 12 chunk 0] — Confidence: 87%</li></ol></div>

            Now answer the USER QUESTION using the context and follow the OUTPUT FORMAT exactly.
            """

            # Step 5: Get response from open ai
            llm_response = get_llm_response(prompt)

            # Step 6: Save response in ChatConversation
            if llm_response:
                ChatConversation.objects.create(
                    chat=chat,
                    sender="bot",
                    message=llm_response,
                )
            chat.is_conversation_active = True
            chat.save()

        conversations = ChatConversation.objects.filter(chat=chat).order_by(
            "created_at"
        )
        context = {
            "team": team,
            "chat": chat,
            "conversations": conversations,
            "previous_chats": previous_chats,
        }
        return render(request, "team/chat_conversation.html", context)

    def post(self, request, *args, **kwargs):
        # --- 1. Identify team and chat ---
        team = Team.objects.filter(
            id=kwargs.get("team_id"), members__user=request.user
        ).first()

        chat = Chat.objects.filter(
            id=kwargs.get("chat_id"), team=team, user=request.user
        ).first()

        # --- 2. Get query and embed it ---
        query = request.POST.get("query", "").strip()
        if not query:
            messages.error(request, "Query cannot be empty.")
            return redirect("chat-conversation", team_id=team.id, chat_id=chat.id)

        query_embedding = get_query_embedding(query)

        # --- 3. Retrieve top document chunks based on similarity ---
        related_document_chunks = (
            DocumentChunk.objects.annotate(
                distance=CosineDistance("embedding", query_embedding)
            )
            .filter(document__team=team)
            .select_related("document")
            .order_by("distance")[:4]
        )

        # --- 4. Fetch recent conversation (last few turns) ---
        N_HISTORY = 8
        recent_convs = ChatConversation.objects.filter(chat=chat).order_by(
            "-created_at"
        )[:N_HISTORY]
        # reverse so oldest -> newest when sending to LLM
        recent_convs = list(reversed(recent_convs))

        # --- 5. Build conversation history text ---
        conversation_text = ""
        for conv in recent_convs:
            speaker = "User" if conv.sender == "user" else "Bot"
            # keep single-line entries to avoid introducing unintended line breaks
            msg_single_line = " ".join(conv.message.splitlines()).strip()
            conversation_text += f"{speaker}: {msg_single_line}\n"

        # --- 6. Build snippet context (with a simple heuristic confidence from distance) ---
        context_parts = []
        for i, chunk in enumerate(related_document_chunks):
            doc = getattr(chunk, "document", None)

            doc_id = getattr(doc, "id", "")
            doc_name = getattr(doc, "name", "Untitled")
            doc_file_name = getattr(getattr(doc, "file", None), "name", "") or ""
            doc_content_type = getattr(doc, "content_type", "") or ""
            doc_size = getattr(doc, "size", "") or ""
            doc_metadata = ""
            try:
                if getattr(doc, "metadata", None):
                    doc_metadata = json.dumps(doc.metadata, ensure_ascii=False)
            except Exception:
                doc_metadata = str(getattr(doc, "metadata", ""))

            doc_created_at = getattr(doc, "created_at", "")
            chunk_index = getattr(chunk, "chunk_index", i)
            distance = getattr(chunk, "distance", None)

            # simple heuristic to convert distance -> estimated confidence (0-100)
            # smaller distance -> higher confidence. Clamp to 0..100.
            try:
                estimated_confidence = int(
                    max(0, min(100, round(100 - (float(distance or 0) * 100))))
                )
            except Exception:
                estimated_confidence = 50

            # Use your model method to build the HTML link; fallback if not available
            doc_html_link = ""
            try:
                doc_html_link = doc.html_document_link()
            except Exception:
                file_url = getattr(getattr(doc, "file", None), "url", "")
                if file_url:
                    doc_html_link = (
                        f'<a href="{file_url}" target="_blank">{doc_name}</a>'
                    )
                else:
                    doc_html_link = doc_name

            header = (
                f"Snippet {i+1}:\n"
                f"Document id: {doc_id}\n"
                f"Document name: {doc_name}\n"
                f"Document file: {doc_file_name}\n"
                f"Document content_type: {doc_content_type}\n"
                f"Document size: {doc_size}\n"
                f"Document metadata: {doc_metadata}\n"
                f"Document created_at: {doc_created_at}\n"
                f"Chunk index: {chunk_index}\n"
                f"Embedding distance: {distance}\n"
                f"Estimated confidence (from distance): {estimated_confidence}\n"
                f"Document html link: {doc_html_link}\n"
            )

            # single-line chunk text to avoid accidental paragraph breaks in the LLM answer
            chunk_text = " ".join(chunk.text.splitlines()).strip()
            context_parts.append(header + "\n" + chunk_text)

        context_text = "\n\n---\n\n".join(context_parts)

        # --- 7. Build improved prompt including conversation history ---
        # Use the user's posted 'query' as the USER QUESTION
        user_query = query

        prompt = f"""
        You are an intelligent assistant that answers using ONLY the provided document snippets and the recent conversation history.

        GUIDELINES:
        - Use ONLY facts contained in the provided snippets and the recent conversation history below. Do not hallucinate or add outside facts.
        - If the answer cannot be found in the provided context, reply exactly: "I don't know."
        - The output MUST follow the exact HTML format described below (no extra commentary, no extra line breaks).

        RECENT CONVERSATION (oldest -> newest):
        {conversation_text}

        DOCUMENT SNIPPETS (each snippet includes a ready-to-use 'Document html link' that is a proper <a> tag):
        {context_text}

        USER QUESTION:
        {user_query}

        OUTPUT FORMAT (required):
        1) A single, clear, factual paragraph answering the user's question. This paragraph must contain no line breaks.
        2) Immediately after the paragraph output a horizontal rule: <hr/>
        3) After the <hr/>, output an HTML sources block exactly as follows:

        <div class="llm-sources">
        <ol>
            <!-- For each source the model used, output one <li> -->
            <li> <document_html_link> — [sources: doc <doc_id> chunk <chunk_index>] — Confidence: <confidence>%</li>
            <!-- repeat for each used snippet -->
        </ol>
        </div>

        RULES FOR THE SOURCES BLOCK:
        - Use only the provided 'Document html link' values; do not invent or change URLs.
        - For each cited snippet, provide the doc id and chunk index that match the snippet header.
        - For Confidence, provide an integer 0–100. You can use the 'Estimated confidence (from distance)' line in each snippet as guidance, but choose values that reflect your internal judgement; order snippets from most to least important.
        - If answering "I don't know.", still include the sources block (it may be empty: <ol></ol>) or include the nearest matches inspected, with low confidence scores.

        Now answer the USER QUESTION following the OUTPUT FORMAT exactly.
        """

        # --- 8. Store existing user query ---
        ChatConversation.objects.create(
            chat=chat,
            sender="user",
            message=query,
        )

        # Step 9: Get response from LLM and save raw HTML (no sanitization as requested)
        llm_response = get_llm_response(prompt)
        if llm_response:
            ChatConversation.objects.create(
                chat=chat,
                sender="bot",
                message=llm_response,
            )

        return redirect("chat-conversation", team_id=team.id, chat_id=chat.id)
